"""Sales by month report in a fictional storefront admin, internal walkthrough for the support team.

    python3 -I scenario.py desktop|phone|outro
"""
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.environ["SCRIPTS"])
from recorder import Demo  # noqa: E402

BASE = "http://localhost:3000/admin"
REPORT = f"{BASE}/reports/sales_by_month"
LAST_MONTH = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
REPORT_LAST_MONTH = f"{REPORT}?month={LAST_MONTH}"
demo = Demo(workdir=Path(__file__).parent)


def row(order_id):
    return f"#sales_row_{order_id}"


def desktop():
    demo.viewport(1440, 900)
    demo.prime(f"{BASE}/reports")
    with demo.take("desktop") as take:
        with take.scene("01_intro") as s:
            s.at("Last")
            demo.scroll(500)
            s.at("new")
            demo.click("a[href*='sales_by_month']")
            time.sleep(2)
        with take.scene("02_rollout") as s:
            s.at("replaces")
            demo.hover("h1")
            s.at("plan")
            demo.move(700, 140, duration=900)
        with take.scene("03_overview") as s:
            s.at("Each")
            demo.hover("tbody tr:first-child td:nth-child(4)")
            s.at("strip")
            demo.move(330, 590, duration=800)
            s.at("average")
            demo.move(560, 630, duration=600)
        with take.scene("04_range") as s:
            s.at("month")
            demo.pick("#month_picker > button", f"#month_picker [data-month='{LAST_MONTH}']", scene=s, cue="last")
        with take.scene("05_columns") as s:
            demo.hover(row(21))
            demo.scroll(250)
            s.at("Open")
            demo.click(f"{row(21)} button.expand")
            s.at("Hover")
            demo.hover(f"{row(21)}_item_75 td.gross .tooltip-trigger")
            s.at("Net", -0.3)
            demo.scroll(-2000)
            demo.hover("thead th:last-child .tooltip-trigger")
        with take.scene("06_refunds") as s:
            demo.hover(f"{row(21)}_item_75 td:nth-child(3)")
            s.at("Untick")
            demo.click("#include_refunds")
            time.sleep(2.5)
            demo.hover("h1")
            s.until(s.length - 0.5)
            demo.click("#include_refunds")
            time.sleep(2)
        with take.scene("07_bundles") as s:
            s.at("bundle")
            demo.type("input[name=keyword]", "Starter kit")
            s.at("default")
            demo.hover("#allocation")
            s.at("month", nth=1)
            demo.click(f"{row(43)} button.expand")
            s.at("labeled")
            demo.hover(f"{row(43)} + tr td")
        with take.scene("08_first") as s:
            demo.pick_native("#allocation", "On the first shipment", scene=s, cue="first")
            demo.click(f"{row(43)} button.expand")
        with take.scene("09_split") as s:
            demo.pick_native("#allocation", "Split across shipments", scene=s, cue="splits")
            demo.click(f"{row(43)} button.expand")
        with take.scene("10_subscriptions") as s:
            demo.open(f"{REPORT_LAST_MONTH}&allocation=last&keyword=Subscription")
            s.at("split")
            demo.click(f"{row(51)} button.expand")
            s.at("records")
            demo.hover(f"{row(51)} + tr td")
            s.until(s.length)
            demo.type("input[name=keyword]", "", settle=2.5)
        with take.scene("11_store") as s:
            demo.pick("#store_filter > button", "#store_filter label:has(input[value='8'])", settle=0,
                      scene=s, cue="Downtown")
            demo.click("#store_filter > button")
            time.sleep(3)
        with take.scene("11b_staff") as s:
            demo.pick("#staff_filter > button", "#staff_filter label:has(input[value='3'])", settle=0,
                      scene=s, cue="Priya")
            demo.click("#staff_filter > button")
            time.sleep(3)
            s.at("buttons")
            demo.hover("#store_filter > button")
        with take.scene("12_export") as s:
            s.at("Export")
            demo.click("#export_button")
            time.sleep(3)
            demo.hover("a[href*='download']", check=False)
        with take.scene("13_limits") as s:
            s.at("Shipping")
            demo.hover("#excluded_shipping_fees")
            s.at("tax")
            demo.move(900, 330, duration=1200)


def phone():
    demo.viewport(390, 844)
    demo.prime(REPORT_LAST_MONTH)
    with demo.take("phone") as take:
        with take.scene("14_phone") as s:
            demo.click("#month_picker > button")
            demo.pick_native("select[aria-label='Date range presets']", "Last quarter", settle=1, scene=s, cue="dropdown")


def outro():
    demo.viewport(1440, 900)
    demo.prime(f"{REPORT_LAST_MONTH}&allocation=split")
    with demo.take("outro") as take:
        with take.scene("15_outro") as s:
            s.at("Every")
            demo.click(f"{row(43)} button.expand")
            s.until(s.length + 1.5)


{"desktop": desktop, "phone": phone, "outro": outro}[sys.argv[1]]()
