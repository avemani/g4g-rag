import gc
import json
import time
import math
import httpx
import random
import optuna
import mlflow
import asyncio
import traceback
from ragas import evaluate
from abc import ABC, abstractmethod
from ragas.run_config import RunConfig
from llm.search_engine.chat_llm import ChatLLM
from ragas import EvaluationDataset, SingleTurnSample
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.metrics import answer_correctness, answer_relevancy, context_precision, context_recall, faithfulness



class BaseRAGASEvaluator(ABC):
    @abstractmethod
    async def init_connection(self):
        raise NotImplementedError
    
    @abstractmethod
    async def warm_up(self):
        raise NotImplementedError
    
    @abstractmethod
    async def predict(self):
        raise NotImplementedError

    @abstractmethod
    async def objective(self):
        raise NotImplementedError
    
    @abstractmethod
    async def run_evaluation(self):
        raise NotImplementedError
        
    @abstractmethod
    async def close_connections(self):
        raise NotImplementedError



class RAGASEvaluator(BaseRAGASEvaluator):
    def __init__(
        self, 
        base_url: str, 
        api_key: str, 
        reranker_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        caching: bool = False,
        tracking_uri: str = 'http://mlflow-server:5000',
        experiment_name: str = 'RAG_Hyperparameter_Tuning'
    ):
        self.base_url = base_url
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.chat_llm = ChatLLM(
            base_url=base_url,
            api_key=api_key,
            reranker_name=reranker_name,
            caching=caching
        )
        self.judge_llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            # model='eval-ollama',
            model='local-ollama',
            temperature=0.0,
            extra_body={'caching': False},
            max_tokens=1000,
            timeout=300,
            max_retries=3
        )
        self.judge_embedding = OpenAIEmbeddings(
            model='ollama-embedding',
            openai_api_base=base_url,
            api_key=api_key,
            check_embedding_ctx_length=False
        )


    async def init_connection(self, postgres_user: str, postgres_password: str) -> bool:
        await self.chat_llm.init_connection(postgres_user=postgres_user, postgres_password=postgres_password)


    async def warm_up(self):
        for _ in range(5):
            query = f'What is {random.randint(1,100)} + {random.randint(1,100)}?'
            await self.chat_llm.generate_answer(query=query)


    async def clear_ollama_vram(self):
        litellm_url = self.base_url.rstrip('/') + '/chat/completions'
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    litellm_url,
                    json={
                        'model': self.judge_llm.model_name,
                        'messages': [{'role': 'user', 'content': 'clear'}],
                        'max_tokens': 1,
                        'keep_alive': 0
                    },
                    timeout=10.0
                )
        except Exception as e:
            print(f'VRAM Clearing Warning: {e}')


    async def predict(self, use_meta: bool, use_kword: bool, use_rerank: bool, k: int, limit: int, t: int) -> tuple[int, float, EvaluationDataset]:
        samples = []

        with open('evaluation/test_data/questions.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

            ln = len(data)
            if ln == 0:
                return 0.0, 0, EvaluationDataset([])
            
            start_time = time.perf_counter()

            for record in data:
                response, retrieved_contexts = await self.chat_llm.generate_answer(
                    query=record['user_input'],
                    use_meta=use_meta,
                    use_kword=use_kword,
                    use_rerank=use_rerank,
                    k=k,
                    limit=limit,
                    t=t,
                    eval=True
                )

                samples.append(
                    SingleTurnSample(
                        user_input=record['user_input'],
                        response=response,
                        retrieved_contexts=retrieved_contexts,
                        reference_contexts=record['reference_contexts'],
                        reference=record['ground_truth']
                    )
                )

            eval_time = time.perf_counter() - start_time
            eval_dataset = EvaluationDataset(samples)

        return eval_time, ln, eval_dataset


    async def objective(self, trial: optuna.Trial) -> float:
        with mlflow.start_run(run_name=f'trial_{trial.number}', nested=True):
            use_meta = trial.suggest_categorical('use_meta', [True, False])
            use_kword = trial.suggest_categorical('use_kword', [True, False])
            use_rerank = trial.suggest_categorical('use_rerank', [True, False])
            limit = trial.suggest_int('limit', 10, 60)
            k = trial.suggest_int('k', 10, 100)
            t = trial.suggest_int('t', 3, 5)

            mlflow.log_params(trial.params)
            mlflow.set_tags({'model': 'Qwen2.5:3b'})

            eval_time, ln, eval_dataset = await self.predict(
                use_meta=use_meta,
                use_kword=use_kword,
                use_rerank=use_rerank,
                k=k,
                limit=limit,
                t=t
            )

            results = evaluate(
                dataset=eval_dataset,
                metrics=[
                    answer_correctness, 
                    answer_relevancy, 
                    context_precision, 
                    context_recall, 
                    faithfulness
                ],
                llm=self.judge_llm,
                embeddings=self.judge_embedding,
                run_config=RunConfig(timeout=300, max_workers=1)
            )

            metric_names = [
                'answer_correctness', 
                'answer_relevancy', 
                'context_precision', 
                'context_recall', 
                'faithfulness'
            ]

            df_details = results.to_pandas()

            results_dict = dict()
            for metric in metric_names:
                if metric in df_details.columns:
                    val = df_details[metric].mean()
                    results_dict[metric] = 0.0 if (val is None or math.isnan(val)) else float(val)
                
            scores = [1 / (val + 1e-8) for val in results_dict.values()]
            harmonic_score = len(scores) / sum(scores) if scores else 0.0

            if not scores:
                return 0.0
            
            harmonic_score = len(scores) / sum(scores)

            all_metrics = {'harmonic_score': harmonic_score} | results_dict | {'overall_latency': eval_time} | {'per_query_latency': eval_time / ln}
            mlflow.log_metrics(all_metrics)

            await self.clear_ollama_vram()
            del eval_dataset
            del results
            del df_details
            gc.collect()

            await asyncio.sleep(30)

            return harmonic_score


    async def run_evaluation(self, n_trials: int = 15):
        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(self.experiment_name)

        study = optuna.create_study(direction='maximize')

        with mlflow.start_run(run_name='Optuna_Optimization'):
            for _ in range(n_trials):
                trial = study.ask()
                try:
                    score = await self.objective(trial)
                    study.tell(trial, score)
                except Exception as e:
                    study.tell(trial, state=optuna.trial.TrialState.FAIL)
                    print(f'Trial {trial.number} failed with error: {e}')
                    traceback.print_exc()

        return study.best_params


    async def close_connections(self):
        await self.chat_llm.close_connection()