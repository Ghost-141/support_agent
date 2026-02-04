import os
import json
import logging
import psycopg
from dotenv import load_dotenv

load_dotenv(".env.example")


DB_URL = os.environ["SUPASEBASE_DB_URL"]

CREATE_TABLES = os.getenv("CREATE_TABLES", "0") == "1"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    with open("products.json", "r", encoding="utf-8") as f:
        products = json.load(f)["products"]

    products_rows = []
    tags_rows = []
    reviews_rows = []

    for p in products:
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
            )
        )

        for tag in p.get("tags", []):
            tags_rows.append((p["id"], tag))

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
                      thumbnail text
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
            # 1) Upsert products
            logger.info("Upserting products: %d", len(products_rows))
            cur.executemany(
                """
                insert into products (
                  id, title, description, category, price, discount_percentage, rating, stock,
                  brand, sku, weight, warranty_information, shipping_information, availability_status,
                  return_policy, minimum_order_quantity, dimensions, meta, thumbnail
                ) values (
                  %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s
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
                  thumbnail = excluded.thumbnail
                """,
                products_rows,
            )

            # 2) Insert tags/reviews
            if tags_rows:
                logger.info("Inserting tags: %d", len(tags_rows))
                cur.executemany(
                    "insert into product_tags (product_id, tag) values (%s, %s) on conflict do nothing",
                    tags_rows,
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
        print("Load complete.")


if __name__ == "__main__":
    main()
