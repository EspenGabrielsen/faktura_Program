"""Start med: python app.py. GUI-et bruker vanlig Tkinter og ttk."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from reportlab.platypus.doctemplate import LayoutError

import database as storage
from invoice_pdf import make_pdf, make_copy


BUTTON_HELP = {
    "Åpne / endre": "Åpner valgt kladd for redigering. For en ferdigstilt faktura åpnes original-PDF-en.",
    "Kopier til ny": "Lager en ny kladd med kunde og varelinjer fra valgt faktura. Originalen beholdes.",
    "Åpne PDF": "Viser original-PDF-en til valgt ferdigstilt faktura i PDF-leseren.",
    "Lagre PDF som …": "Lagrer original-PDF-en som en fil du kan legge ved en e-post.",
    "Skriv ut kopi …": "Åpner en PDF merket KOPI på hver side. Velg Skriv ut (Ctrl+P) i PDF-leseren.",
    "Innbetaling": "Registrerer betalingsdato og innbetalt beløp på valgt faktura. Du kan også registrere delbetaling.",
    "Påminnelse": "Lager en PDF-påminnelse for valgt forfalt faktura med restbeløp, uten gebyr eller renter. Send den selv.",
    "Slett kladd": "Sletter valgt kladd etter bekreftelse. Ferdigstilte fakturaer kan ikke slettes.",
    "Innstillinger": "Her legger du inn gårdens opplysninger, kontonummer, MVA-registrering, logo og betalingsfrist.",
    "Sikkerhetskopi …": "Kopierer hele databasen med kunder, priser, logo og faktura-PDF-er til en fil du velger.",
    "Sett start etter gammelt system …": "Oppgi år og siste brukte løpenummer i det gamle systemet. Kan bare endres før årets første faktura ferdigstilles her.",
    "Lagre kladd": "Lagrer fakturaen slik at du kan arbeide videre senere. Den får ikke fakturanummer ennå.",
    "Ferdigstill og lag PDF": "Tildeler fakturanummer, låser innholdet og arkiverer PDF-en. Fakturaen sendes ikke automatisk.",
    "Legg til linje": "Legg inn en vare eller tjeneste manuelt, eller velg fra prislisten. Antall, pris og MVA kan justeres.",
    "Endre linje": "Åpner den valgte varelinjen for å endre beskrivelse, antall, pris eller MVA.",
    "Fjern linje": "Fjerner den valgte varelinjen fra kladden. Lagre kladden for å beholde endringen.",
    "Endre kunde": "Endrer kundekortet. Ferdigstilte fakturaer beholder de opprinnelige kundeopplysningene.",
    "Endre pris": "Endrer varen eller tjenesten i prislisten. Prisene på eksisterende fakturaer beholdes.",
    "Fjern logo": "Fjerner logoen fra innstillingene når du trykker Lagre. Arkiverte faktura-PDF-er beholdes.",
}


def add_tooltip(widget, text):
    """Vis kort hjelp etter et halvt sekund, uten å flytte tastaturfokus."""
    pending = None
    tip = None

    def hide(event=None):
        nonlocal pending, tip
        if pending is not None:
            widget.after_cancel(pending)
            pending = None
        if tip is not None:
            tip.destroy()
            tip = None

    def show():
        nonlocal pending, tip
        pending = None
        if not widget.winfo_ismapped():
            return
        tip = tk.Toplevel(widget)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.transient(widget.winfo_toplevel())
        tip.attributes("-topmost", True)
        tk.Label(tip, text=text, wraplength=330, justify="left", background="#fff8dc",
                 foreground="#252525", relief="solid", borderwidth=1,
                 padx=10, pady=7).pack()
        tip.update_idletasks()
        x = min(widget.winfo_rootx(), widget.winfo_screenwidth() - tip.winfo_reqwidth() - 8)
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        if y + tip.winfo_reqheight() > widget.winfo_screenheight():
            y = widget.winfo_rooty() - tip.winfo_reqheight() - 6
        tip.geometry(f"+{max(0, x)}+{max(0, y)}")
        tip.deiconify()

    def enter(event):
        nonlocal pending
        hide()
        pending = widget.after(600, show)

    widget.bind("<Enter>", enter, add="+")
    for event in ("<Leave>", "<ButtonPress>", "<Unmap>", "<Destroy>"):
        widget.bind(event, hide, add="+")


def help_button(parent, **options):
    button = ttk.Button(parent, **options)
    text = BUTTON_HELP.get(options.get("text"))
    if text:
        add_tooltip(button, text)
    return button


def attempt(action):
    """Vis feil i vinduet i stedet for at et knappeklikk feiler lydløst."""
    try:
        action()
    except (ValueError, OSError, storage.sqlite3.Error, LayoutError) as error:
        focused = root.focus_get()
        parent = focused.winfo_toplevel() if focused else root
        messagebox.showerror("Kunne ikke fullføre", str(error), parent=parent)


def selected(table):
    selection = table.selection()
    if not selection:
        raise ValueError("Velg en rad først.")
    return int(selection[0])


def fields_frame(parent, fields):
    """fields: (nøkkel, etikett, startverdi, eventuelle valg)."""
    frame = ttk.Frame(parent, padding=12)
    frame.pack(fill="x")
    frame.columnconfigure(1, weight=1)
    variables = {}
    for row, (key, label, value, choices) in enumerate(fields):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        variable = tk.StringVar(value=value)
        variables[key] = variable
        if choices:
            widget = ttk.Combobox(frame, textvariable=variable, values=choices, state="readonly")
        else:
            widget = ttk.Entry(frame, textvariable=variable)
        widget.grid(row=row, column=1, sticky="ew", pady=3)
    return variables


def values(variables):
    return {key: variable.get().strip() for key, variable in variables.items()}


def new_window(title, parent=None):
    """Alle egne vinduer åpnes foran riktig foreldrevindu."""
    parent = parent or root
    window = tk.Toplevel(parent)
    window.title(title)
    window.transient(parent)

    def bring_forward():
        window.lift()
        window.focus_set()

    window.after_idle(bring_forward)
    return window


def edit_form(title, fields, save, parent=None):
    window = new_window(title, parent)
    variables = fields_frame(window, fields)

    def commit():
        save(values(variables))
        refresh()
        window.destroy()

    help_button(window, text="Lagre", command=lambda: attempt(commit)).pack(pady=12)
    if parent is not None and parent is not root:
        window.grab_set()
    return window, variables


def customer_editor(edit=False):
    customer_id = selected(trees["customers"]) if edit else None
    seller, _ = storage.get_settings(db)
    data = dict(db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()) if edit else {}
    specifications = [
        ("kind", "Kundetype", "Privatperson", ["Privatperson", "Virksomhet"]),
        ("name", "Navn *", "", None), ("address", "Adresse", "", None),
        ("postal_code", "Postnummer", "", None), ("city", "Poststed", "", None),
        ("country", "Land", "Norge", None), ("org_number", "Organisasjonsnummer", "", None),
        ("email", "Faktura-e-post", "", None), ("phone", "Telefon", "", None),
        ("contact", "Kontaktperson", "", None), ("reference", "Kundens referanse", "", None),
        ("days", "Betalingsfrist (dager)", seller["days"], None),
    ]
    fields = [(key, label, data.get(key, default), choices) for key, label, default, choices in specifications]
    edit_form(f"Kunde {customer_id}" if edit else "Ny kunde – nummer tildeles ved lagring",
              fields, lambda item: storage.save_customer(db, item, customer_id))


def product_editor(edit=False):
    product_id = selected(trees["products"]) if edit else None
    item = dict(db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()) if edit else {}
    seller, _ = storage.get_settings(db)
    default_vat = "25 %" if seller["mva"] else "Ikke MVA-registrert"
    fields = [("name", "Vare/tjeneste", item.get("name", ""), None),
              ("unit", "Enhet", item.get("unit", "stk"), None),
              ("price", "Pris eks. MVA (kr)", storage.money(item.get("price", 0)), None),
              ("vat", "MVA-type", item.get("vat", default_vat), list(storage.VAT))]
    edit_form("Endre pris" if edit else "Ny vare/tjeneste", fields,
              lambda data: storage.save_product(db, **data, product_id=product_id))


def settings_editor():
    seller, logo = storage.get_settings(db)
    chosen_logo = [logo]
    fields = [(key, label, seller[key], None) for key, label in [
        ("name", "Gårdens navn"), ("address", "Adresse"), ("postal_code", "Postnummer"),
        ("city", "Poststed"), ("org_number", "Organisasjonsnummer"), ("account", "Kontonummer"),
        ("email", "E-post"), ("phone", "Telefon"), ("days", "Standard betalingsfrist (dager)")]]
    fields.append(("mva", "MVA-registrert", "Ja" if seller["mva"] else "Nei", ["Ja", "Nei"]))

    def save(data):
        data["mva"] = data["mva"] == "Ja"
        storage.save_settings(db, data, chosen_logo[0])

    window, _ = edit_form("Gårdens innstillinger", fields, save)
    status = tk.StringVar(value="Logo lagret" if logo else "Ingen logo")

    def choose_logo():
        path = filedialog.askopenfilename(parent=window, filetypes=[("Logo", "*.png *.jpg *.jpeg")])
        if path:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
            chosen_logo[0] = Path(path).read_bytes()
            status.set(Path(path).name)

    def remove_logo():
        chosen_logo[0] = None
        status.set("Ingen logo")

    ttk.Label(window, textvariable=status).pack()
    help_button(window, text="Velg logo …", command=lambda: attempt(choose_logo)).pack(pady=4)
    help_button(window, text="Fjern logo", command=remove_logo).pack(pady=4)

    def starting_number():
        year = simpledialog.askinteger("Overgang fra gammelt system", "År:", initialvalue=date.today().year, parent=window)
        if year is None:
            return
        last = simpledialog.askinteger("Overgang fra gammelt system", "Siste brukte løpenummer (uten årstall):", minvalue=0, parent=window)
        if last is not None:
            storage.set_year_start(db, year, last)
            messagebox.showinfo("Nummerering", f"Neste nummer blir {storage.invoice_number(year, last + 1)}", parent=window)

    help_button(window, text="Sett start etter gammelt system …", command=lambda: attempt(starting_number)).pack(pady=8)


def invoice_editor(edit=False, copy=False):
    row = None
    if edit or copy:
        row = db.execute("SELECT * FROM invoices WHERE id=?", (selected(trees["invoices"]),)).fetchone()
        if row["number"] and not copy:
            open_pdf(row)
            return
    customers = {f"{c['id']} – {c['name']}": c for c in db.execute("SELECT * FROM customers ORDER BY name")}
    if not customers:
        raise ValueError("Opprett en kunde først.")
    details = json.loads(row["details"]) if row else {}
    draft_id = [row["id"] if row and not copy else None]
    today = date.today().isoformat()
    seller, _ = storage.get_settings(db)
    initial_customer = next((label for label, customer in customers.items() if customer["id"] == details.get("customer_id")), next(iter(customers)))
    customer = customers[initial_customer]
    window = new_window("Fakturakladd")
    window.geometry("940x720")
    fields = [
        ("customer", "Kunde", initial_customer, list(customers)),
        ("date", "Fakturadato (ÅÅÅÅ-MM-DD)", today if copy else details.get("date", today), None),
        ("due", "Forfall (ÅÅÅÅ-MM-DD)", (date.today() + timedelta(days=customer["days"])).isoformat() if copy else details.get("due", (date.today() + timedelta(days=customer["days"])).isoformat()), None),
        ("delivery_date", "Leveringsdato (ÅÅÅÅ-MM-DD)", today if copy else details.get("delivery_date", today), None),
        ("delivery_place", "Leveringssted", details.get("delivery_place", seller["address"]), None),
        ("reference", "Kundens referanse", details.get("reference", customer["reference"]), None),
        ("note", "Merknad", details.get("note", ""), None),
    ]
    variables = fields_frame(window, fields)

    def customer_changed(*_):
        customer = customers[variables["customer"].get()]
        try:
            due = date.fromisoformat(variables["date"].get()) + timedelta(days=customer["days"])
            variables["due"].set(due.isoformat())
        except ValueError:
            pass
        variables["reference"].set(customer["reference"])

    variables["customer"].trace_add("write", customer_changed)
    lines = [dict(line) for line in details.get("lines", [])]
    table = ttk.Treeview(window, columns=("text", "quantity", "price", "vat", "sum"), show="headings", height=8)
    for key, title, width in [("text", "Beskrivelse", 330), ("quantity", "Antall", 90), ("price", "Pris eks. MVA", 120), ("vat", "MVA-type", 160), ("sum", "Netto", 110)]:
        table.heading(key, text=title)
        table.column(key, width=width)
    table.pack(fill="both", expand=True, padx=12)
    total_label = tk.StringVar()

    def refresh_lines():
        table.delete(*table.get_children())
        calculated, net, tax = storage.calculate(lines)
        for index, line in enumerate(calculated):
            table.insert("", "end", iid=str(index), values=(line["description"], f"{line['quantity']} {line['unit']}", storage.money(line["price"]), line["vat"], storage.money(line["net"])))
        total_label.set(f"Netto {storage.money(net)} kr   MVA {storage.money(tax)} kr   Totalt {storage.money(net + tax)} kr")

    def line_editor(edit_line=False):
        index = selected(table) if edit_line else None
        line = lines[index] if edit_line else {}
        products = {f"{p['id']} – {p['name']}": p for p in db.execute("SELECT * FROM products ORDER BY name")}
        default_vat = "25 %" if seller["mva"] else "Ikke MVA-registrert"
        line_fields = [("product", "Fra prislisten", "Manuell linje", ["Manuell linje", *products]),
                       ("description", "Beskrivelse", line.get("description", ""), None),
                       ("quantity", "Antall", line.get("quantity", "1"), None),
                       ("unit", "Enhet", line.get("unit", "stk"), None),
                       ("price", "Pris eks. MVA (kr)", storage.money(line.get("price", 0)), None),
                       ("vat", "MVA-type", line.get("vat", default_vat), list(storage.VAT))]

        def save_line(data):
            data.pop("product")
            data["price"] = storage.cents(data["price"])
            storage.calculate([data])
            if index is None:
                lines.append(data)
            else:
                lines[index] = data
            refresh_lines()

        _, line_variables = edit_form("Fakturalinje", line_fields, save_line, parent=window)

        def product_changed(*_):
            product = products.get(line_variables["product"].get())
            if product:
                for key in ("unit", "vat"):
                    line_variables[key].set(product[key])
                line_variables["description"].set(product["name"])
                line_variables["price"].set(storage.money(product["price"]))

        line_variables["product"].trace_add("write", product_changed)

    def remove_line():
        lines.pop(selected(table))
        refresh_lines()

    def save(issued=False):
        data = values(variables)
        data["customer_id"] = customers[data.pop("customer")]["id"]
        data["lines"] = lines
        for key in ("date", "due", "delivery_date"):
            date.fromisoformat(data[key])
        draft_id[0] = storage.save_draft(db, data, draft_id[0])
        if issued:
            if not messagebox.askyesno("Ferdigstill faktura", "Fakturaen får nummer og låses. Ferdigstill nå?", parent=window):
                refresh()
                return
            number = storage.issue_invoice(db, draft_id[0], make_pdf)
            messagebox.showinfo("Faktura lagret", f"Faktura {number} og PDF er lagret.", parent=window)
        refresh()
        window.destroy()

    bar = ttk.Frame(window, padding=12)
    bar.pack(fill="x")
    for label, action in [("Legg til linje", lambda: line_editor()), ("Endre linje", lambda: line_editor(True)), ("Fjern linje", remove_line)]:
        help_button(bar, text=label, command=lambda fn=action: attempt(fn)).pack(side="left", padx=3)
    ttk.Label(window, textvariable=total_label).pack(pady=8)
    buttons = ttk.Frame(window, padding=12)
    buttons.pack(fill="x")
    help_button(buttons, text="Lagre kladd", command=lambda: attempt(save)).pack(side="left")
    help_button(buttons, text="Ferdigstill og lag PDF", command=lambda: attempt(lambda: save(True))).pack(side="right")
    refresh_lines()


def export_pdf(row=None):
    if row is None:
        row = db.execute("SELECT * FROM invoices WHERE id=?", (selected(trees["invoices"]),)).fetchone()
    if not row["pdf"]:
        raise ValueError("Ferdigstill fakturaen før du eksporterer PDF.")
    path = filedialog.asksaveasfilename(initialfile=f"Faktura-{row['number']}.pdf", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    if path:
        Path(path).write_bytes(row["pdf"])


def open_pdf(row=None):
    if row is None:
        row = db.execute("SELECT * FROM invoices WHERE id=?", (selected(trees["invoices"]),)).fetchone()
    if not row["pdf"]:
        raise ValueError("Kladden har ingen ferdig PDF.")
    open_pdf_file(row["pdf"], f"Faktura-{row['number']}")


def print_copy():
    row = db.execute("SELECT * FROM invoices WHERE id=?", (selected(trees["invoices"]),)).fetchone()
    if not row["pdf"]:
        raise ValueError("Ferdigstill fakturaen før du skriver ut en kopi.")
    copy = make_copy(row["pdf"])
    open_pdf_file(copy, f"Faktura-{row['number']}-KOPI")
    messagebox.showinfo("Utskrift av kopi", "En PDF merket KOPI åpnes i PDF-leseren.\nVelg Skriv ut (Ctrl+P) der.", parent=root)


def open_pdf_file(pdf, name):
    # Unik fil: unngår å overskrive andre dokumenter i temp-mappen.
    with tempfile.NamedTemporaryFile(prefix=f"{name}-", suffix=".pdf", delete=False) as file:
        file.write(pdf)
        path = file.name
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


def register_payment():
    invoice_id = selected(trees["invoices"])
    row = next(row for row in storage.invoices(db) if row["id"] == invoice_id)
    if not row["number"]:
        raise ValueError("Kladden er ikke utstedt.")
    edit_form("Registrer innbetaling", [("paid_on", "Betalingsdato (ÅÅÅÅ-MM-DD)", date.today().isoformat(), None),
                                       ("amount", "Beløp (kr)", storage.money(row["total"] - row["paid"]), None)],
              lambda data: storage.add_payment(db, invoice_id, **data))


def reminder():
    row = next(row for row in storage.invoices(db) if row["id"] == selected(trees["invoices"]))
    details = json.loads(row["details"])
    if not row["number"] or row["total"] <= row["paid"] or details["due"] >= date.today().isoformat():
        raise ValueError("Velg en forfalt faktura med restbeløp.")
    details.update(reminder=True, remaining=row["total"] - row["paid"])
    path = filedialog.asksaveasfilename(initialfile=f"Påminnelse-{row['number']}.pdf", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    if path:
        # Påminnelsen endrer ikke originalfakturaen. Ingen gebyr eller rente.
        Path(path).write_bytes(make_pdf(details, row["number"]))
        if messagebox.askyesno("Påminnelse lagret", "Vil du registrere påminnelsen som sendt nå?"):
            with db:
                db.execute("INSERT INTO reminders(invoice_id, sent_on) VALUES (?, ?)", (row["id"], date.today().isoformat()))
            refresh()


def backup():
    path = filedialog.asksaveasfilename(initialfile=f"faktura-backup-{date.today()}.sqlite3", defaultextension=".sqlite3")
    if path:
        if Path(path).resolve() == database_path.resolve():
            raise ValueError("Velg en annen fil enn databasen som er i bruk.")
        destination = storage.sqlite3.connect(path)
        try:
            db.backup(destination)
        finally:
            destination.close()
        messagebox.showinfo("Sikkerhetskopi", "Database med kunder, priser, logo og PDF-er er kopiert.")


def delete_draft():
    invoice_id = selected(trees["invoices"])
    row = db.execute("SELECT number FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if row["number"]:
        raise ValueError("Utstedte fakturaer kan ikke slettes. Velg en kladd.")
    if messagebox.askyesno("Slett kladd", "Vil du slette den valgte kladden?"):
        storage.delete_draft(db, invoice_id)
        refresh()


def sort_invoices(column):
    global invoice_sort, invoice_descending
    invoice_descending = not invoice_descending if column == invoice_sort else False
    invoice_sort = column
    refresh()


def refresh():
    selections = {key: tree.selection() for key, tree in trees.items()}
    for tree in trees.values():
        tree.delete(*tree.get_children())
    query = search.get().casefold()
    for customer in db.execute("SELECT * FROM customers ORDER BY name"):
        if query in f"{customer['id']} {customer['name']} {customer['email']}".casefold():
            trees["customers"].insert("", "end", iid=customer["id"], values=(customer["id"], customer["name"], customer["city"], customer["email"]))
    for product in db.execute("SELECT * FROM products ORDER BY name"):
        if query in product["name"].casefold():
            trees["products"].insert("", "end", iid=product["id"], values=(product["name"], product["unit"], storage.money(product["price"]), product["vat"]))
    rows = []
    years = set()
    for invoice in storage.invoices(db):
        details = json.loads(invoice["details"])
        year = details["date"][:4]
        years.add(year)
        customer = details.get("customer") or db.execute("SELECT * FROM customers WHERE id=?", (details["customer_id"],)).fetchone()
        name = customer["name"]
        number = invoice["number"] or f"Kladd {invoice['id']}"
        if query not in f"{number} {name}".casefold():
            continue
        if not invoice["number"]:
            status = "Kladd"
            _, net, tax = storage.calculate(details["lines"])
            total = net + tax
        else:
            total = invoice["total"]
            status = "Betalt" if invoice["paid"] >= total else "Forfalt" if details["due"] < date.today().isoformat() else "Ubetalt"
        allowed_statuses = {"Alle": {"Kladd", "Ubetalt", "Forfalt", "Betalt"},
                            "Kladder": {"Kladd"}, "Ubetalte": {"Ubetalt", "Forfalt"},
                            "Forfalte": {"Forfalt"}, "Betalte": {"Betalt"}}
        if status not in allowed_statuses[status_filter.get()]:
            continue
        if year_filter.get() != "Alle år" and year_filter.get() != year:
            continue
        last_reminder = db.execute("SELECT MAX(sent_on) FROM reminders WHERE invoice_id=?", (invoice["id"],)).fetchone()[0] or ""
        displayed = (number, name, details["date"], details["due"], storage.money(total), storage.money(total - invoice["paid"]), status, last_reminder)
        number_order = (invoice["year"] or 0, invoice["sequence"] or invoice["id"])
        rows.append((invoice["id"], displayed, number_order))
    year_box.configure(values=["Alle år", *sorted(years, reverse=True)])
    columns = list(trees["invoices"]["columns"])
    index = columns.index(invoice_sort)

    def sort_key(row):
        if invoice_sort == "Nummer":
            return row[2]
        if invoice_sort in ("Totalt", "Restbeløp"):
            return storage.cents(row[1][index])
        return row[1][index].casefold()

    for invoice_id, displayed, _ in sorted(rows, key=sort_key, reverse=invoice_descending):
        trees["invoices"].insert("", "end", iid=invoice_id, values=displayed)
    for column in columns:
        arrow = (" ▼" if invoice_descending else " ▲") if column == invoice_sort else ""
        trees["invoices"].heading(column, text=column + arrow)
    for key, selection in selections.items():
        remaining = [item for item in selection if trees[key].exists(item)]
        trees[key].selection_set(remaining)


def setup_styles():
    # Clam støtter knappfarger også på Windows, i motsetning til enkelte native temaer.
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", rowheight=28)
    colors = {
        "Invoice": ("#e4eef9", "#173f68", "#ccdef1"),
        "Document": ("#eee7f5", "#52356d", "#dfd0ee"),
        "Payment": ("#e2f1e8", "#235c3c", "#cbe5d6"),
        "Delete": ("#f8e8e6", "#8b2923", "#f0d0cc"),
        "Primary": ("#245b8c", "#ffffff", "#19466e"),
    }
    for name, (background, foreground, active) in colors.items():
        style.configure(f"{name}.TButton", background=background, foreground=foreground,
                        padding=(12, 7))
        style.map(f"{name}.TButton", background=[("pressed", active), ("active", active)],
                  foreground=[("disabled", "#777777")])
        style.configure(f"{name}.TLabelframe.Label", foreground=foreground)


def invoice_toolbar(parent):
    """Tre små grupper er lettere å finne frem i enn én lang knapperad."""
    groups = [
        ("Faktura", "Invoice", [
            ("Ny faktura", invoice_editor, "Primary"),
            ("Åpne / endre", lambda: invoice_editor(True), "Invoice"),
            ("Kopier til ny", lambda: invoice_editor(copy=True), "Invoice")]),
        ("PDF og utskrift", "Document", [
            ("Åpne PDF", open_pdf, "Document"),
            ("Lagre PDF som …", export_pdf, "Document"),
            ("Skriv ut kopi …", print_copy, "Document")]),
        ("Betaling og oppfølging", "Payment", [
            ("Innbetaling", register_payment, "Payment"),
            ("Påminnelse", reminder, "Payment")]),
    ]
    for column, (title, group_style, actions) in enumerate(groups):
        parent.columnconfigure(column, weight=1, uniform="actions")
        group = ttk.LabelFrame(parent, text=title, padding=8, style=f"{group_style}.TLabelframe")
        group.grid(row=0, column=column, sticky="nsew", padx=4)
        for label, action, button_style in actions:
            help_button(group, text=label, style=f"{button_style}.TButton",
                       command=lambda fn=action: attempt(fn)).pack(fill="x", pady=3)


def main():
    global root, db, trees, search, database_path
    global status_filter, year_filter, year_box, invoice_sort, invoice_descending
    if len(sys.argv) == 3 and sys.argv[1] == "--database":
        database_path = Path(sys.argv[2]).expanduser()
    elif len(sys.argv) != 1:
        raise SystemExit("Bruk: python app.py [--database FIL]")
    elif sys.platform == "win32":
        database_path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Gardsfaktura" / "faktura.sqlite3"
    else:
        database_path = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "gardsfaktura" / "faktura.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    db = storage.connect(database_path)
    root = tk.Tk()
    root.title("Gårdsfaktura")
    root.geometry("1100x740")
    root.minsize(900, 600)
    setup_styles()
    header = ttk.Frame(root, padding=12)
    header.pack(fill="x")
    ttk.Label(header, text="Gårdsfaktura", font=("", 18, "bold")).pack(side="left")
    help_button(header, text="Innstillinger", command=lambda: attempt(settings_editor)).pack(side="right", padx=4)
    help_button(header, text="Sikkerhetskopi …", command=lambda: attempt(backup)).pack(side="right", padx=4)
    search = tk.StringVar()
    ttk.Label(header, text="Søk:").pack(side="left", padx=(30, 5))
    ttk.Entry(header, textvariable=search, width=30).pack(side="left")
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=8)
    trees = {}
    status_filter = tk.StringVar(value="Alle")
    year_filter = tk.StringVar(value="Alle år")
    invoice_sort, invoice_descending = "Dato", True
    tabs = [
        ("invoices", "Fakturaer", ["Nummer", "Kunde", "Dato", "Forfall", "Totalt", "Restbeløp", "Status", "Påminnelse sendt"],
         []),
        ("customers", "Kunder", ["Kundenummer", "Navn", "Poststed", "E-post"],
         [("Ny kunde", customer_editor), ("Endre kunde", lambda: customer_editor(True))]),
        ("products", "Prisliste", ["Vare/tjeneste", "Enhet", "Pris eks. MVA", "MVA-type"],
         [("Ny vare/tjeneste", product_editor), ("Endre pris", lambda: product_editor(True))]),
    ]
    for key, title, columns, actions in tabs:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        bar = ttk.Frame(frame, padding=8)
        bar.pack(fill="x")
        if key == "invoices":
            invoice_toolbar(bar)
        for label, action in actions:
            button_style = "Primary.TButton" if label.startswith("Ny ") else "Invoice.TButton"
            help_button(bar, text=label, style=button_style,
                       command=lambda fn=action: attempt(fn)).pack(side="left", padx=3)
        if key == "invoices":
            filters = ttk.Frame(frame, padding=(8, 0, 8, 8))
            filters.pack(fill="x")
            ttk.Label(filters, text="Vis:").pack(side="left", padx=(0, 5))
            ttk.Combobox(filters, textvariable=status_filter, state="readonly", width=14,
                         values=["Alle", "Kladder", "Ubetalte", "Forfalte", "Betalte"]).pack(side="left")
            ttk.Label(filters, text="År:").pack(side="left", padx=(16, 5))
            year_box = ttk.Combobox(filters, textvariable=year_filter, state="readonly", width=10, values=["Alle år"])
            year_box.pack(side="left")
            help_button(filters, text="Slett kladd", style="Delete.TButton", command=lambda: attempt(delete_draft)).pack(side="right")
            ttk.Label(filters, text="Klikk på en kolonneoverskrift for å sortere").pack(side="left", padx=16)
        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True)
        tree = ttk.Treeview(body, columns=columns, show="headings", selectmode="browse")
        for column in columns:
            tree.heading(column, text=column)
            if key == "invoices":
                tree.heading(column, command=lambda col=column: sort_invoices(col))
            tree.column(column, width=130, minwidth=65)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        trees[key] = tree
    ttk.Label(root, text=f"Database: {database_path}", padding=8).pack(anchor="w")
    search.trace_add("write", lambda *_: refresh())
    status_filter.trace_add("write", lambda *_: refresh())
    year_filter.trace_add("write", lambda *_: refresh())
    refresh()
    try:
        root.mainloop()
    finally:
        db.close()


if __name__ == "__main__":
    main()
