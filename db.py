import os
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import requests
import json


load_dotenv()
load_dotenv(".env.example", override=False)


def _build_db_url() -> str:
    url = os.getenv("SUPASEBASE_DB_URL")
    if url:
        return url
    host = os.getenv("SUPASEBASE_DB_HOST")
    name = os.getenv("SUPASEBASE_DB_NAME")
    user = os.getenv("SUPASEBASE_DB_USER")
    password = os.getenv("SUPASEBASE_DB_PASSWORD")
    port = os.getenv("SUPASEBASE_DB_PORT")
    if not all([host, name, user, password, port]):
        raise RuntimeError(
            "Missing DB settings. Set SUPASEBASE_DB_URL or the SUPASEBASE_DB_* parts."
        )
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


DB_URL = _build_db_url()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "embeddinggemma:300m")


def _connect():
    return psycopg.connect(DB_URL, row_factory=dict_row)


def _embed_query(text: str) -> List[float]:
    resp = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    emb = resp.json().get("embedding")
    if not emb:
        raise RuntimeError("No embedding returned for query.")
    return emb


def _to_vector_literal(vec: List[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def search_products(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []
    q = f"%{query.strip()}%"
    sql = """
    with tag_agg as (
      select product_id, array_agg(tag order by tag) as tags
      from product_tags
      group by product_id
    ),
    review_agg as (
      select product_id, avg(rating)::float as avg_rating, count(*) as review_count
      from product_reviews
      group by product_id
    ),
    image_agg as (
      select product_id, array_agg(url order by url) as images
      from product_images
      group by product_id
    )
    select
      p.id,
      p.title,
      p.description,
      p.category,
      p.price,
      p.rating,
      p.stock,
      p.brand,
      p.sku,
      p.availability_status,
      p.shipping_information,
      p.return_policy,
      coalesce(t.tags, '{}') as tags,
      coalesce(i.images, '{}') as images,
      coalesce(r.avg_rating, p.rating) as avg_rating,
      coalesce(r.review_count, 0) as review_count
    from products p
    left join tag_agg t on t.product_id = p.id
    left join image_agg i on i.product_id = p.id
    left join review_agg r on r.product_id = p.id
    where
      p.title ilike %(q)s
      or p.description ilike %(q)s
      or p.category ilike %(q)s
      or p.brand ilike %(q)s
      or p.sku ilike %(q)s
      or exists (
        select 1 from product_tags pt
        where pt.product_id = p.id and pt.tag ilike %(q)s
      )
    order by
      case when p.title ilike %(q)s then 0 else 1 end,
      p.rating desc nulls last
    limit %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"q": q, "limit": limit})
            return cur.fetchall()


def search_products_hybrid(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []
    q = f"%{query.strip()}%"
    qvec = _to_vector_literal(_embed_query(query.strip()))
    sql = """
    with tag_agg as (
      select product_id, array_agg(tag order by tag) as tags
      from product_tags
      group by product_id
    ),
    review_agg as (
      select product_id, avg(rating)::float as avg_rating, count(*) as review_count
      from product_reviews
      group by product_id
    ),
    image_agg as (
      select product_id, array_agg(url order by url) as images
      from product_images
      group by product_id
    )
    select
      p.id,
      p.title,
      p.description,
      p.category,
      p.price,
      p.rating,
      p.stock,
      p.brand,
      p.sku,
      p.availability_status,
      p.shipping_information,
      p.return_policy,
      coalesce(t.tags, '{}') as tags,
      coalesce(i.images, '{}') as images,
      coalesce(r.avg_rating, p.rating) as avg_rating,
      coalesce(r.review_count, 0) as review_count,
      (p.embedding <=> %(qvec)s::vector) as vector_distance,
      (
        p.title ilike %(q)s
        or p.description ilike %(q)s
        or p.category ilike %(q)s
        or p.brand ilike %(q)s
        or p.sku ilike %(q)s
        or exists (
          select 1 from product_tags pt
          where pt.product_id = p.id and pt.tag ilike %(q)s
        )
      ) as keyword_match
    from products p
    left join tag_agg t on t.product_id = p.id
    left join image_agg i on i.product_id = p.id
    left join review_agg r on r.product_id = p.id
    where p.embedding is not null
    order by
      keyword_match desc,
      vector_distance asc nulls last
    limit %(limit)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"q": q, "qvec": qvec, "limit": limit})
            return cur.fetchall()


def get_product_by_id(product_id: int) -> Dict[str, Any] | None:
    sql = """
    select *
    from products
    where id = %(id)s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": product_id})
            return cur.fetchone()
