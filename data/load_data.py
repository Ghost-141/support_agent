import os
import json
import logging
import psycopg
import requests
from dotenv import load_dotenv

load_dotenv(".env.example")


DB_URL = os.environ["SUPASEBASE_DB_URL"]

CREATE_TABLES = os.getenv("CREATE_TABLES", "0") == "1"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ---- Embedding config (Ollama local) ----
# Install & run Ollama, then pull an embedding model:
#   ollama pull nomic-embed-text
#
# This endpoint returns embeddings from your local machine:
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/embeddings")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "embeddinggemma:300m")

# If you already created embedding vector with a specific dimension, set it here
# nomic-embed-text is typically 768-d (verify in your environment)

EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "128"))


def build_content(p: dict) -> str:
    """Create a compact, high-signal text to embed for search/RAG."""
    tags = p.get("tags") or []
    dims = p.get("dimensions") or {}
    meta = p.get("meta") or {}

    parts = [
        p.get("title"),
        f"Brand: {p.get('brand')}" if p.get("brand") else None,
        f"Category: {p.get('category')}" if p.get("category") else None,
        f"SKU: {p.get('sku')}" if p.get("sku") else None,
        (
            f"Availability: {p.get('availabilityStatus')}"
            if p.get("availabilityStatus")
            else None
        ),
        (
            f"Warranty: {p.get('warrantyInformation')}"
            if p.get("warrantyInformation")
            else None
        ),
        (
            f"Shipping: {p.get('shippingInformation')}"
            if p.get("shippingInformation")
            else None
        ),
        f"Return: {p.get('returnPolicy')}" if p.get("returnPolicy") else None,
        f"Price: {p.get('price')}" if p.get("price") is not None else None,
        (
            f"Discount: {p.get('discountPercentage')}"
            if p.get("discountPercentage") is not None
            else None
        ),
        f"Rating: {p.get('rating')}" if p.get("rating") is not None else None,
        f"Stock: {p.get('stock')}" if p.get("stock") is not None else None,
        p.get("description"),
        ("Tags: " + ", ".join(tags)) if tags else None,
        ("Dimensions: " + json.dumps(dims, ensure_ascii=False)) if dims else None,
        ("Meta: " + json.dumps(meta, ensure_ascii=False)) if meta else None,
    ]
    content = " | ".join([x for x in parts if x and str(x).strip()])
    return content.strip()


def ollama_embed(texts: list[str]) -> list[list[float]]:
    """
    Ollama /api/embeddings is single-text per request.
    We'll loop; for large data you can parallelize or use a different embed server.
    """
    out = []
    for t in texts:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": t},
            timeout=60,
        )
        resp.raise_for_status()
        emb = resp.json().get("embedding")
        if not emb:
            raise RuntimeError(f"No embedding returned for text (len={len(t)})")
        out.append(emb)
    return out


def to_vector_literal(vec: list[float]) -> str:
    """
    Safest way without extra adapters:
    pgvector accepts string like: '[0.1,0.2,...]'
    """
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main():
    with open("products.json", "r", encoding="utf-8") as f:
        products = json.load(f)["products"]

    products_rows = []
    tags_rows = []
    images_rows = []
    reviews_rows = []

    # We'll also track (id, content) for embedding generation
    id_and_content = []

    for p in products:
        content = build_content(p)
        id_and_content.append((p["id"], content))

        products_rows.append(
            (
                p["id"],
                p.get("title"),
                p.get("description"),
                p.get("category"),
                p.get("price"),
                p.get("discountPercentage"),
                p.get("rating"),
                p.get("stock"),
                p.get("brand"),
                p.get("sku"),
                p.get("weight"),
                p.get("warrantyInformation"),
                p.get("shippingInformation"),
                p.get("availabilityStatus"),
                p.get("returnPolicy"),
                p.get("minimumOrderQuantity"),
                json.dumps(p.get("dimensions"), ensure_ascii=False),
                json.dumps(p.get("meta"), ensure_ascii=False),
                p.get("thumbnail"),
                content,  # NEW
            )
        )

        for tag in p.get("tags", []):
            tags_rows.append((p["id"], tag))

        for url in p.get("images", []):
            images_rows.append((p["id"], url))

        for r in p.get("reviews", []):
            reviews_rows.append(
                (
                    p["id"],
                    r.get("rating"),
                    r.get("comment"),
                    r.get("date"),
                    r.get("reviewerName"),
                    r.get("reviewerEmail"),
                )
            )

    with psycopg.connect(DB_URL) as conn:
        if CREATE_TABLES:
            logger.info("Creating tables (CREATE_TABLES=1).")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    create extension if not exists vector;

                    create table if not exists products (
                      id int primary key,
                      title text,
                      description text,
                      category text,
                      price numeric,
                      discount_percentage numeric,
                      rating numeric,
                      stock int,
                      brand text,
                      sku text,
                      weight int,
                      warranty_information text,
                      shipping_information text,
                      availability_status text,
                      return_policy text,
                      minimum_order_quantity int,
                      dimensions jsonb,
                      meta jsonb,
                      thumbnail text,
                      content text,
                      embedding vector
                    );

                    create table if not exists product_tags (
                      product_id int references products(id) on delete cascade,
                      tag text,
                      primary key (product_id, tag)
                    );

                    create table if not exists product_images (
                      product_id int references products(id) on delete cascade,
                      url text,
                      primary key (product_id, url)
                    );

                    create table if not exists product_reviews (
                      id bigserial primary key,
                      product_id int references products(id) on delete cascade,
                      rating int,
                      comment text,
                      date timestamptz,
                      reviewer_name text,
                      reviewer_email text
                    );
                    """
                )
                conn.commit()

        with conn.cursor() as cur:
            # 1) Upsert products (now includes content)
            logger.info("Upserting products: %d", len(products_rows))
            cur.executemany(
                """
                insert into products (
                  id, title, description, category, price, discount_percentage, rating, stock,
                  brand, sku, weight, warranty_information, shipping_information, availability_status,
                  return_policy, minimum_order_quantity, dimensions, meta, thumbnail,
                  content
                ) values (
                  %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s,
                  %s
                )
                on conflict (id) do update set
                  title = excluded.title,
                  description = excluded.description,
                  category = excluded.category,
                  price = excluded.price,
                  discount_percentage = excluded.discount_percentage,
                  rating = excluded.rating,
                  stock = excluded.stock,
                  brand = excluded.brand,
                  sku = excluded.sku,
                  weight = excluded.weight,
                  warranty_information = excluded.warranty_information,
                  shipping_information = excluded.shipping_information,
                  availability_status = excluded.availability_status,
                  return_policy = excluded.return_policy,
                  minimum_order_quantity = excluded.minimum_order_quantity,
                  dimensions = excluded.dimensions,
                  meta = excluded.meta,
                  thumbnail = excluded.thumbnail,
                  content = excluded.content
                """,
                products_rows,
            )

            # 2) Insert tags/images/reviews
            if tags_rows:
                logger.info("Inserting tags: %d", len(tags_rows))
                cur.executemany(
                    "insert into product_tags (product_id, tag) values (%s, %s) on conflict do nothing",
                    tags_rows,
                )

            if images_rows:
                logger.info("Inserting images: %d", len(images_rows))
                cur.executemany(
                    "insert into product_images (product_id, url) values (%s, %s) on conflict do nothing",
                    images_rows,
                )

            if reviews_rows:
                logger.info("Inserting reviews: %d", len(reviews_rows))
                cur.executemany(
                    """
                    insert into product_reviews (
                      product_id, rating, comment, date, reviewer_name, reviewer_email
                    ) values (%s, %s, %s, %s, %s, %s)
                    """,
                    reviews_rows,
                )

            conn.commit()

        # 3) Generate embeddings + batch update products.embedding
        # Do this outside the cursor context if you want, but keep same connection.
        with conn.cursor() as cur:
            for batch in chunked(id_and_content, BATCH_SIZE):
                ids = [x[0] for x in batch]
                texts = [x[1] for x in batch]

                embs = ollama_embed(texts)

                # Sanity check dimension (optional but helpful)
                for e in embs:
                    if len(e) != EMBED_DIM:
                        raise ValueError(
                            f"Embedding dim mismatch: got {len(e)} expected {EMBED_DIM}. "
                            f"Fix EMBED_DIM or your products.embedding vector(n)."
                        )

                update_rows = [(to_vector_literal(e), pid) for e, pid in zip(embs, ids)]

                logger.info("Updating embeddings for %d products", len(update_rows))
                cur.executemany(
                    """
                    update products
                    set embedding = %s::vector
                    where id = %s
                    """,
                    update_rows,
                )

                conn.commit()
                print(f"Embedded & updated {len(batch)} products.")

    print("Load + embedding complete.")


if __name__ == "__main__":
    main()
