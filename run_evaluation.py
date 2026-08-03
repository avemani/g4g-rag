import asyncio
from evaluation.config.settings import settings
from evaluation.core.evaluation import RAGASEvaluator


evaluator = RAGASEvaluator(
    base_url=settings.litellm_url,
    api_key=settings.litellm_api_key,
    reranker_name=settings.reranker_name,
    caching=settings.caching,
    tracking_uri=settings.tracking_uri,
    experiment_name=settings.experiment_name
)


async def evaluate(evaluator, settings):
    await evaluator.init_connection(
        postgres_user=settings.db_user,
        postgres_password=settings.db_password
    )
    await evaluator.warm_up()
    await evaluator.run_evaluation(n_trials=15)
    await evaluator.close_connections()


if __name__ == '__main__':
    asyncio.run(evaluate(evaluator, settings))