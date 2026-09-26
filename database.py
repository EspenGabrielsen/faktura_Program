"""SQLite og små funksjoner for kunder, priser og fakturaer."""

import json
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


VAT = {"25 %": 25, "15 %": 15, "12 %": 12,
       "0 % (fritatt)": 0, "Unntatt MVA": 0, "Ikke MVA-registrert": 0}


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, address TEXT NOT NULL, postal_code TEXT NOT NULL,
            city TEXT NOT NULL, country TEXT NOT NULL, org_number TEXT NOT NULL,
            email TEXT NOT NULL, phone TEXT NOT NULL, contact TEXT NOT NULL,
            reference TEXT NOT NULL, days INTEGER NOT NULL, kind TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, unit TEXT NOT NULL, price INTEGER NOT NULL,
            vat TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            details TEXT NOT NULL, logo BLOB
        );
        CREATE TABLE IF NOT EXISTS counters (
            year INTEGER PRIMARY KEY, value INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE, year INTEGER, sequence INTEGER,
            details TEXT NOT NULL, total INTEGER NOT NULL DEFAULT 0,
            pdf BLOB, issued_at TEXT,
            UNIQUE(year, sequence)
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL REFERENCES invoices(id),
            paid_on TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount > 0)
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL REFERENCES invoices(id), sent_on TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS lock_invoice_update
        BEFORE UPDATE ON invoices WHEN OLD.number IS NOT NULL
        BEGIN SELECT RAISE(ABORT, 'Utstedte fakturaer kan ikke endres'); END;
        CREATE TRIGGER IF NOT EXISTS lock_invoice_delete
        BEFORE DELETE ON invoices WHEN OLD.number IS NOT NULL
        BEGIN SELECT RAISE(ABORT, 'Utstedte fakturaer kan ikke slettes'); END;
    """)
    return db


def decimal_value(text):
    try:
        value = Decimal(str(text).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError("Skriv et gyldig tall.") from None
    if not value.is_finite():
        raise ValueError("Skriv et endelig tall.")
    return value


def cents(text):
    return int((decimal_value(text) * 100).quantize(Decimal("1"), ROUND_HALF_UP))


def money(amount):
    return f"{Decimal(amount) / 100:,.2f}".replace(",", " ").replace(".", ",")


def org_valid(number):
    if len(number) != 9 or not number.isascii() or not number.isdigit():
        return False
    check = 11 - sum(int(n) * w for n, w in zip(number[:8], (3, 2, 7, 6, 5, 4, 3, 2))) % 11
    return (0 if check == 11 else check) == int(number[-1])


def save_customer(db, values, customer_id=None):
    values = dict(values)
    values["name"] = values["name"].strip()
    values["org_number"] = values["org_number"].replace(" ", "")
    if not values["name"]:
        raise ValueError("Kunden må ha et navn.")
    if values["org_number"] and values["country"] == "Norge" and not org_valid(values["org_number"]):
        raise ValueError("Organisasjonsnummeret er ikke gyldig.")
    values["days"] = int(values["days"])
    if not 0 <= values["days"] <= 365:
        raise ValueError("Betalingsfristen må være mellom 0 og 365 dager.")
    fields = list(values)
    with db:
        if customer_id is None:
            sql = f"INSERT INTO customers ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})"
            return db.execute(sql, list(values.values())).lastrowid
        sql = "UPDATE customers SET " + ",".join(f"{f}=?" for f in fields) + " WHERE id=?"
        db.execute(sql, [*values.values(), customer_id])
    return customer_id


def save_product(db, name, unit, price, vat, product_id=None):
    amount = cents(price)
    if not name.strip() or amount < 0 or vat not in VAT:
        raise ValueError("Oppgi varenavn, ikke-negativ pris og MVA-type.")
    with db:
        if product_id is None:
            return db.execute("INSERT INTO products(name, unit, price, vat) VALUES (?, ?, ?, ?)",
                              (name.strip(), unit, amount, vat)).lastrowid
        db.execute("UPDATE products SET name=?, unit=?, price=?, vat=? WHERE id=?",
                   (name.strip(), unit, amount, vat, product_id))
    return product_id


def get_settings(db):
    row = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
    if row:
        return json.loads(row["details"]), row["logo"]
    return dict(name="", address="", postal_code="", city="", org_number="",
                account="", email="", phone="", mva=False, days="14"), None


def save_settings(db, values, logo):
    if not 0 <= int(values["days"]) <= 365:
        raise ValueError("Betalingsfrist må være mellom 0 og 365 dager.")
    with db:
        db.execute("INSERT OR REPLACE INTO settings VALUES (1, ?, ?)",
                   (json.dumps(values, ensure_ascii=False), logo))


def calculate(lines):
    result = []
    for line in lines:
        quantity = decimal_value(line["quantity"])
        if quantity <= 0 or line["price"] < 0 or not line["description"].strip():
            raise ValueError("Hver linje må ha beskrivelse, positivt antall og ikke-negativ pris.")
        net = int((quantity * line["price"]).quantize(Decimal("1"), ROUND_HALF_UP))
        tax = int((Decimal(net) * VAT[line["vat"]] / 100).quantize(Decimal("1"), ROUND_HALF_UP))
        result.append(dict(line, net=net, tax=tax))
    return result, sum(x["net"] for x in result), sum(x["tax"] for x in result)


def invoice_number(year, sequence):
    if sequence < 1:
        raise ValueError("Sekvensnummer må være positivt.")
    if sequence <= 9999:
        return f"{year}{sequence:04d}"
    block, remainder = divmod(sequence - 10000, 1000)
    letters = ""
    block += 1
    while block:
        block, digit = divmod(block - 1, 26)
        letters = chr(65 + digit) + letters
    return f"{year}{letters}{remainder:03d}"


def save_draft(db, details, draft_id=None):
    encoded = json.dumps(details, ensure_ascii=False)
    with db:
        if draft_id is None:
            return db.execute("INSERT INTO invoices(details) VALUES (?)", (encoded,)).lastrowid
        row = db.execute("UPDATE invoices SET details=? WHERE id=? AND number IS NULL",
                         (encoded, draft_id))
        if row.rowcount != 1:
            raise ValueError("Fakturaen er allerede ferdigstilt eller finnes ikke.")
    return draft_id


def delete_draft(db, draft_id):
    """Bare kladder kan slettes. Utstedte fakturaer beholdes i arkivet."""
    with db:
        result = db.execute("DELETE FROM invoices WHERE id=? AND number IS NULL", (draft_id,))
        if result.rowcount != 1:
            raise ValueError("Bare eksisterende kladder kan slettes.")


def issue_invoice(db, draft_id, make_pdf):
    """Tildel nummer og arkiver PDF atomisk. PDF-feil ruller alt tilbake."""
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM invoices WHERE id=?", (draft_id,)).fetchone()
        if row is None or row["number"]:
            raise ValueError("Velg en fakturakladd.")
        details = json.loads(row["details"])
        customer = db.execute("SELECT * FROM customers WHERE id=?", (details["customer_id"],)).fetchone()
        if customer is None:
            raise ValueError("Velg en kunde.")
        customer = dict(customer)
        if not customer["org_number"] and not all(customer[k].strip() for k in ("address", "postal_code", "city", "country")):
            raise ValueError("Kunden må ha adresse eller organisasjonsnummer.")
        seller, logo = get_settings(db)
        if not all(seller[k].strip() for k in ("name", "address", "postal_code", "city", "account")) or not org_valid(seller["org_number"].replace(" ", "")):
            raise ValueError("Fyll inn gårdens navn, adresse, gyldig organisasjonsnummer og kontonummer i Innstillinger.")
        invoice_date = date.fromisoformat(details["date"])
        if date.fromisoformat(details["due"]) < invoice_date:
            raise ValueError("Forfall kan ikke være før fakturadato.")
        date.fromisoformat(details["delivery_date"])
        if not details["delivery_place"].strip() or not details["lines"]:
            raise ValueError("Oppgi leveringssted og minst én varelinje.")
        if not seller["mva"] and any(x["vat"] != "Ikke MVA-registrert" for x in details["lines"]):
            raise ValueError("Gården er ikke merket MVA-registrert. Bruk typen «Ikke MVA-registrert».")
        if seller["mva"] and any(x["vat"] == "Ikke MVA-registrert" for x in details["lines"]):
            raise ValueError("Gården er MVA-registrert. Velg sats, fritatt eller unntatt for hver linje.")
        lines, net, tax = calculate(details["lines"])
        details.update(customer=customer, seller=seller, lines=lines, net=net, tax=tax)
        year = invoice_date.year
        db.execute("INSERT OR IGNORE INTO counters VALUES (?, 0)", (year,))
        db.execute("UPDATE counters SET value=value+1 WHERE year=?", (year,))
        sequence = db.execute("SELECT value FROM counters WHERE year=?", (year,)).fetchone()[0]
        number = invoice_number(year, sequence)
        pdf = make_pdf(details, number, logo)
        db.execute("UPDATE invoices SET number=?, year=?, sequence=?, details=?, total=?, pdf=?, issued_at=? WHERE id=?",
                   (number, year, sequence, json.dumps(details, ensure_ascii=False), net + tax,
                    pdf, date.today().isoformat(), draft_id))
    return number


def invoices(db):
    return db.execute("""SELECT i.*, COALESCE((SELECT SUM(amount) FROM payments
        WHERE invoice_id=i.id), 0) AS paid FROM invoices i ORDER BY id DESC""").fetchall()


def add_payment(db, invoice_id, paid_on, amount):
    date.fromisoformat(paid_on)
    amount = cents(amount)
    row = db.execute("SELECT number, total FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    paid = db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?", (invoice_id,)).fetchone()[0]
    if not row or not row["number"] or amount <= 0 or paid + amount > row["total"]:
        raise ValueError("Beløpet må være positivt og ikke overstige restbeløpet på en utstedt faktura.")
    with db:
        db.execute("INSERT INTO payments(invoice_id, paid_on, amount) VALUES (?, ?, ?)",
                   (invoice_id, paid_on, amount))


def set_year_start(db, year, last_sequence):
    """Engangsoppsett ved overgang fra gammelt system, før første utstedelse."""
    year, last_sequence = int(year), int(last_sequence)
    if not 2000 <= year <= 9999 or last_sequence < 0:
        raise ValueError("Oppgi gyldig år og siste løpenummer.")
    with db:
        if db.execute("SELECT 1 FROM invoices WHERE year=?", (year,)).fetchone():
            raise ValueError("Årets serie er allerede i bruk og kan ikke endres.")
        db.execute("INSERT OR REPLACE INTO counters VALUES (?, ?)", (year, last_sequence))
