#!/bin/bash
set -e

echo "Initializing databases and users..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER $WEBAPP_USER_DB WITH PASSWORD '$WEBAPP_PASSWORD_DB';
    CREATE USER $LLMDB_USER WITH PASSWORD '$LLMDB_PASS';
    CREATE USER $MLFLOW_USER_DB WITH PASSWORD '$MLFLOW_PASSWORD_DB';

    CREATE DATABASE geekdb OWNER $POSTGRES_USER;
    CREATE DATABASE litellm OWNER $LLMDB_USER;
    CREATE DATABASE mlflow OWNER $MLFLOW_USER_DB;

    GRANT ALL PRIVILEGES ON DATABASE geekdb TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE litellm TO $LLMDB_USER;
    GRANT ALL PRIVILEGES ON DATABASE mlflow TO $MLFLOW_USER_DB;
EOSQL

echo "Initializing schemas and extensions in geekdb..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "geekdb" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    CREATE SCHEMA IF NOT EXISTS vectors;

    CREATE TABLE IF NOT EXISTS vectors.geek_rag_1024 (
        id BIGSERIAL PRIMARY KEY,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        subtitle TEXT NOT NULL,
        main_order INT NOT NULL,
        sub_order INT NOT NULL,
        text_data TEXT NOT NULL,
        embedding halfvec(1024) NOT NULL,
        fts_tokens tsvector NOT NULL GENERATED ALWAYS AS (
            to_tsvector('english', title || E'\n' || subtitle || E'\n' || text_data)
        ) STORED
    );

    CREATE INDEX IF NOT EXISTS trgm_idx_title 
        ON vectors.geek_rag_1024 USING GIN (title gin_trgm_ops);

    CREATE INDEX IF NOT EXISTS trgm_idx_subtitle 
        ON vectors.geek_rag_1024 USING GIN (subtitle gin_trgm_ops);

    CREATE INDEX IF NOT EXISTS hnsw_idx_embedding 
        ON vectors.geek_rag_1024 USING hnsw (embedding halfvec_cosine_ops) 
        WITH (m = 16, ef_construction = 64);

    CREATE INDEX IF NOT EXISTS gin_idx_fts 
        ON vectors.geek_rag_1024 USING GIN (fts_tokens);

    CREATE SCHEMA IF NOT EXISTS webapp;
    GRANT ALL PRIVILEGES ON SCHEMA webapp TO $WEBAPP_USER_DB;

    ALTER DEFAULT PRIVILEGES IN SCHEMA webapp 
    GRANT ALL ON TABLES TO $WEBAPP_USER_DB;

    ALTER DEFAULT PRIVILEGES IN SCHEMA webapp 
    GRANT ALL ON SEQUENCES TO $WEBAPP_USER_DB;

    CREATE TABLE IF NOT EXISTS webapp.chat_history(
        id BIGSERIAL PRIMARY KEY,
        user_id INT NOT NULL,
        text_message TEXT NOT NULL,
        message_type SMALLINT NOT NULL
    );

    GRANT USAGE ON SCHEMA vectors TO $WEBAPP_USER_DB;
    GRANT SELECT ON TABLE vectors.geek_rag_1024 TO $WEBAPP_USER_DB;
EOSQL

echo "Database initialization complete!"
