"""
QueryAI — Database Seed Script.
Populates the analytics business database with rich, realistic data:
- Regions (North America, Europe, APAC, LATAM)
- Product Categories & Subcategories
- Products with prices and SKUs
- Customers with segments and lifetime values
- Employees with departments and salaries
- Orders spanning multiple quarters
- Order Items linked to products
"""
import random
from datetime import date, timedelta
from sqlalchemy import text
from app.database.connection import biz_engine
from app.core.logging import get_logger

log = get_logger(__name__)


def seed_database():
    """Populate database with sample analytics data."""
    with biz_engine.connect() as conn:
        # Check if already seeded
        try:
            res = conn.execute(text("SELECT COUNT(*) FROM customers"))
            count = res.scalar()
            if count and count > 0:
                log.info("Database already contains data", customer_count=count)
                return
        except Exception:
            pass

        log.info("Seeding analytics database...")

        # 1. Regions
        regions = [
            ("North America", "United States", "USD"),
            ("Western Europe", "United Kingdom", "GBP"),
            ("Asia Pacific", "Singapore", "SGD"),
            ("Latin America", "Brazil", "BRL"),
        ]
        for name, country, curr in regions:
            conn.execute(
                text("INSERT INTO regions (name, country, currency) VALUES (:n, :c, :curr)"),
                {"n": name, "c": country, "curr": curr},
            )

        # 2. Categories
        categories = [
            ("Enterprise Software", "B2B SaaS and Enterprise software tools"),
            ("Cloud Infrastructure", "Cloud compute, storage, and networking services"),
            ("Security & Compliance", "Cybersecurity and compliance monitoring"),
            ("Developer Tools", "IDEs, CI/CD pipelines, and SDKs"),
            ("Professional Services", "Consulting, onboarding, and custom integrations"),
        ]
        for name, desc in categories:
            conn.execute(
                text("INSERT INTO categories (name, description) VALUES (:n, :d)"),
                {"n": name, "d": desc},
            )

        # 3. Products
        products = [
            ("Cloud Database Enterprise", "SKU-CLD-001", 1, 1200.00, 400.00, 500),
            ("Real-Time Analytics Platform", "SKU-ANL-002", 1, 2500.00, 800.00, 300),
            ("Kubernetes Mesh Manager", "SKU-K8S-003", 2, 850.00, 250.00, 1000),
            ("Identity & Access Shield", "SKU-SEC-004", 3, 450.00, 120.00, 1500),
            ("API Gateway Enterprise", "SKU-API-005", 4, 600.00, 180.00, 800),
            ("AI Assistant Copilot Suite", "SKU-AI-006", 1, 3500.00, 950.00, 400),
            ("Enterprise Onboarding Package", "SKU-SVC-007", 5, 5000.00, 2000.00, 100),
        ]
        for name, sku, cat_id, price, cost, stock in products:
            conn.execute(
                text("INSERT INTO products (name, sku, category_id, unit_price, cost_price, stock_quantity) "
                     "VALUES (:n, :sku, :cat, :p, :c, :s)"),
                {"n": name, "sku": sku, "cat": cat_id, "p": price, "c": cost, "s": stock},
            )

        # 4. Employees
        departments = [
            ("Sales", "Account Executive", 95000.00),
            ("Sales", "Enterprise Sales Director", 160000.00),
            ("Engineering", "Staff Software Engineer", 175000.00),
            ("Engineering", "Data Architect", 165000.00),
            ("Customer Success", "Senior Solutions Architect", 125000.00),
            ("Marketing", "Growth Marketing Lead", 110000.00),
        ]
        names = [
            ("Sarah", "Connor"), ("John", "Doe"), ("Elena", "Rostova"),
            ("Marcus", "Aurelius"), ("Amina", "Kahn"), ("Liam", "Chen")
        ]
        for i, (dept, role, salary) in enumerate(departments):
            fn, ln = names[i % len(names)]
            email = f"{fn.lower()}.{ln.lower()}@queryai.internal"
            conn.execute(
                text("INSERT INTO employees (first_name, last_name, email, department, role, salary, region_id, hire_date) "
                     "VALUES (:fn, :ln, :e, :d, :r, :s, :reg, :h)"),
                {"fn": fn, "ln": ln, "e": email, "d": dept, "r": role, "s": salary, "reg": (i % 4) + 1, "h": "2023-01-15"},
            )

        # 5. Customers
        customer_data = [
            ("Acme Corporation", "Enterprise", 185000.00),
            ("Global Dynamics", "Enterprise", 240000.00),
            ("Stark Industries", "Enterprise", 395000.00),
            ("Cyberdyne Systems", "Corporate", 88000.00),
            ("Initech Corp", "SMB", 32000.00),
            ("Umbrella Pharma", "Corporate", 115000.00),
            ("Hooli Cloud", "Enterprise", 290000.00),
            ("Pied Piper", "SMB", 45000.00),
            ("Massive Dynamic", "Enterprise", 310000.00),
            ("Wayne Enterprises", "Enterprise", 450000.00),
        ]
        for i, (company, segment, ltv) in enumerate(customer_data):
            parts = company.split()
            fn, ln = parts[0], parts[1] if len(parts) > 1 else "Tech"
            email = f"contact@{company.lower().replace(' ', '')}.com"
            conn.execute(
                text("INSERT INTO customers (first_name, last_name, email, region_id, segment, lifetime_value, acquisition_date) "
                     "VALUES (:fn, :ln, :e, :reg, :seg, :ltv, :acq)"),
                {"fn": fn, "ln": ln, "e": email, "reg": (i % 4) + 1, "seg": segment, "ltv": ltv, "acq": "2023-06-01"},
            )

        # 6. Orders & Order Items
        base_date = date(2024, 1, 1)
        for order_idx in range(1, 25):
            order_date = base_date + timedelta(days=order_idx * 14)
            cust_id = (order_idx % 10) + 1
            emp_id = (order_idx % 6) + 1
            num_items = random.randint(1, 3)
            subtotal = 0.0

            # Create Order
            order_num = f"ORD-2024-{order_idx:04d}"
            conn.execute(
                text("INSERT INTO orders (order_number, customer_id, employee_id, order_date, status, total_amount, payment_method) "
                     "VALUES (:num, :cid, :eid, :od, 'Completed', 0.0, 'Credit Card')"),
                {"num": order_num, "cid": cust_id, "eid": emp_id, "od": order_date},
            )

            # Order items
            for item_idx in range(num_items):
                prod_id = ((order_idx + item_idx) % 7) + 1
                qty = random.randint(1, 5)
                unit_price = [1200.0, 2500.0, 850.0, 450.0, 600.0, 3500.0, 5000.0][prod_id - 1]
                total_price = qty * unit_price
                subtotal += total_price

                conn.execute(
                    text("INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price) "
                         "VALUES (:oid, :pid, :q, :up, :tp)"),
                    {"oid": order_idx, "pid": prod_id, "q": qty, "up": unit_price, "tp": total_price},
                )

            # Update order total
            conn.execute(
                text("UPDATE orders SET total_amount = :amt WHERE id = :oid"),
                {"amt": subtotal, "oid": order_idx},
            )

        conn.commit()
        log.info("Database seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
