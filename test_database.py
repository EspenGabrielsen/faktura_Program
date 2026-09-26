"""Kontroller av fakturabeløp, nummerserier og uforanderlig arkiv."""

import json
import re
import sqlite3
import unittest
from io import BytesIO
from pypdf import PdfReader

import database as storage
from invoice_pdf import make_pdf, make_copy


class InvoiceTests(unittest.TestCase):
    def setUp(self):
        self.db = storage.connect(":memory:")
        self.customer = dict(name="Testkunde ÆØÅ", address="Testveien 1", postal_code="0123",
                             city="Oslo", country="Norge", org_number="", email="", phone="",
                             contact="", reference="", days=14, kind="Privatperson")
        self.customer_id = storage.save_customer(self.db, self.customer)
        self.seller = dict(name="Testgård", address="Gårdsveien 1", postal_code="3340", city="Åmot",
                           org_number="974760673", account="1234.56.78901", email="", phone="",
                           mva=True, days="14")
        storage.save_settings(self.db, self.seller, None)
        self.details = dict(customer_id=self.customer_id, date="2026-09-26", due="2026-10-10",
                            delivery_date="2026-09-26", delivery_place="Testgård", reference="",
                            note="", lines=[dict(description="Testvare", quantity="1,5", unit="kg",
                                                 price=10001, vat="15 %")])

    def tearDown(self):
        self.db.close()

    def draft(self):
        return storage.save_draft(self.db, self.details)

    def test_rounding_and_mixed_vat(self):
        lines = self.details["lines"] + [dict(description="Arbeid", quantity="2", unit="time", price=10000, vat="25 %")]
        calculated, net, tax = storage.calculate(lines)
        self.assertEqual(calculated[0]["net"], 15002)
        self.assertEqual(calculated[0]["tax"], 2250)
        self.assertEqual((net, tax), (35002, 7250))

    def test_number_overflow_and_new_year(self):
        for sequence, expected in [(9999, "20269999"), (10000, "2026A000"), (10999, "2026A999"),
                                   (11000, "2026B000"), (35999, "2026Z999"), (36000, "2026AA000")]:
            self.assertEqual(storage.invoice_number(2026, sequence), expected)
        storage.set_year_start(self.db, 2026, 9999)
        self.assertEqual(storage.issue_invoice(self.db, self.draft(), make_pdf), "2026A000")
        self.details.update(date="2027-01-01", due="2027-01-15")
        self.assertEqual(storage.issue_invoice(self.db, self.draft(), make_pdf), "20270001")

    def test_failed_pdf_does_not_consume_number(self):
        invoice_id = self.draft()

        def fail(*_):
            raise OSError("PDF-feil")

        with self.assertRaises(OSError):
            storage.issue_invoice(self.db, invoice_id, fail)
        self.assertIsNone(self.db.execute("SELECT number FROM invoices").fetchone()[0])
        self.assertEqual(storage.issue_invoice(self.db, invoice_id, make_pdf), "20260001")

    def test_delete_draft_does_not_consume_number_or_delete_issued_invoice(self):
        draft_id = self.draft()
        storage.delete_draft(self.db, draft_id)
        self.assertEqual(storage.invoices(self.db), [])
        invoice_id = self.draft()
        self.assertEqual(storage.issue_invoice(self.db, invoice_id, make_pdf), "20260001")
        with self.assertRaises(ValueError):
            storage.delete_draft(self.db, invoice_id)
        self.assertEqual(storage.invoices(self.db)[0]["number"], "20260001")

    def test_original_survives_customer_and_settings_changes(self):
        invoice_id = self.draft()
        storage.issue_invoice(self.db, invoice_id, make_pdf)
        original = self.db.execute("SELECT * FROM invoices").fetchone()
        storage.save_customer(self.db, dict(self.customer, name="Endret kunde"), self.customer_id)
        storage.save_settings(self.db, dict(self.seller, name="Endret gård"), None)
        row = self.db.execute("SELECT * FROM invoices").fetchone()
        self.assertEqual(row["pdf"], original["pdf"])
        self.assertEqual(json.loads(row["details"])["customer"]["name"], "Testkunde ÆØÅ")
        self.assertEqual(json.loads(row["details"])["seller"]["name"], "Testgård")
        self.assertTrue(row["pdf"].startswith(b"%PDF-"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE invoices SET total=1 WHERE id=?", (invoice_id,))
        self.db.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
        self.db.rollback()

    def test_double_issue_and_counter_reset_are_rejected(self):
        invoice_id = self.draft()
        storage.issue_invoice(self.db, invoice_id, make_pdf)
        with self.assertRaises(ValueError):
            storage.issue_invoice(self.db, invoice_id, make_pdf)
        with self.assertRaises(ValueError):
            storage.set_year_start(self.db, 2026, 0)

    def test_partial_payment_and_overpayment(self):
        invoice_id = self.draft()
        storage.issue_invoice(self.db, invoice_id, make_pdf)
        storage.add_payment(self.db, invoice_id, "2026-10-01", "50,00")
        row = storage.invoices(self.db)[0]
        self.assertEqual(row["paid"], 5000)
        self.assertEqual(row["total"] - row["paid"], 12252)
        with self.assertRaises(ValueError):
            storage.add_payment(self.db, invoice_id, "2026-10-02", "200,00")

    def test_non_registered_seller_cannot_charge_vat(self):
        storage.save_settings(self.db, dict(self.seller, mva=False), None)
        with self.assertRaises(ValueError):
            storage.issue_invoice(self.db, self.draft(), make_pdf)

    def test_missing_customer_address_stops_issue(self):
        storage.save_customer(self.db, dict(self.customer, address=""), self.customer_id)
        with self.assertRaises(ValueError):
            storage.issue_invoice(self.db, self.draft(), make_pdf)

    def test_backup_contains_document_and_logo(self):
        storage.save_settings(self.db, self.seller, b"test-logo")
        storage.issue_invoice(self.db, self.draft(), lambda *_: b"%PDF-test")
        destination = sqlite3.connect(":memory:")
        self.db.backup(destination)
        self.assertEqual(destination.execute("SELECT pdf FROM invoices").fetchone()[0], b"%PDF-test")
        self.assertEqual(destination.execute("SELECT logo FROM settings").fetchone()[0], b"test-logo")
        destination.close()

    def test_multi_page_invoice(self):
        self.details["lines"] *= 100
        storage.issue_invoice(self.db, self.draft(), make_pdf)
        pdf = self.db.execute("SELECT pdf FROM invoices").fetchone()[0]
        self.assertGreater(len(re.findall(rb"/Type\s*/Page\b", pdf)), 1)

    def test_print_copy_marks_every_page_and_preserves_original(self):
        self.details["lines"] *= 60
        storage.issue_invoice(self.db, self.draft(), make_pdf)
        original = self.db.execute("SELECT pdf FROM invoices").fetchone()[0]
        copy = make_copy(original)
        original_pages = PdfReader(BytesIO(original)).pages
        copy_pages = PdfReader(BytesIO(copy)).pages
        self.assertGreater(len(copy_pages), 1)
        self.assertEqual(len(original_pages), len(copy_pages))
        for original_page, copy_page in zip(original_pages, copy_pages):
            self.assertNotIn("KOPI", original_page.extract_text())
            self.assertIn("KOPI", copy_page.extract_text())
            self.assertIn(original_page.extract_text().strip(), copy_page.extract_text())
        self.assertEqual(self.db.execute("SELECT pdf FROM invoices").fetchone()[0], original)


if __name__ == "__main__":
    unittest.main()
