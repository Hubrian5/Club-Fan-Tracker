import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
import time
import json
import os
import csv
import easyocr
from datetime import datetime, timedelta
from PIL import Image

REGION_FILE = "selected_region.json"
reader = easyocr.Reader(['en'], gpu=False)

# ---------- STEP 1: Focus Uma Musume Window ----------
def focus_umamusume():
    try:
        window = gw.getWindowsWithTitle("Umamusume")[0]
        window.activate()
        print("✅ Focused 'Umamusume' window.")
        time.sleep(2)
    except IndexError:
        print("❌ Couldn't find 'Umamusume' window. Make sure it's open.")
        exit()

# ---------- STEP 2: Select and Capture Region ----------
start_point = None
end_point = None
drawing = False
region = None

def mouse_callback(event, x, y, flags, param):
    global start_point, end_point, drawing, region
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_point = (x, y)
        end_point = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        end_point = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_point = (x, y)
        x1, y1 = start_point
        x2, y2 = end_point
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        region = (x1, y1, x2 - x1, y2 - y1)

def select_region():
    global region
    print("🖱️ Drag to select the OCR region, then press any key to confirm.")
    screenshot = pyautogui.screenshot()
    img = np.array(screenshot)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    clone = img.copy()

    cv2.namedWindow("Select Region", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Select Region", mouse_callback)

    while True:
        temp_img = clone.copy()
        if start_point and end_point:
            cv2.rectangle(temp_img, start_point, end_point, (0, 255, 0), 2)
        cv2.imshow("Select Region", temp_img)
        if cv2.waitKey(1) != -1:
            break

    cv2.destroyAllWindows()

    if region:
        with open(REGION_FILE, "w") as f:
            json.dump(region, f)
        print(f"✅ Region saved: {region}")
    else:
        print("❌ No region selected.")

    return region

def capture_selected_region(region, verbose=True):
    if region:
        screenshot = pyautogui.screenshot(region=region)
        screenshot.save("club_list_capture.png")
        if verbose:
            print(f"✅ Saved screenshot as 'club_list_capture.png'")
            print(f"🧭 Region coordinates: {region}")
        return "club_list_capture.png"
    else:
        if verbose:
            print("❌ No region selected.")
        return None

def load_saved_region():
    if os.path.exists(REGION_FILE):
        try:
            with open(REGION_FILE, "r") as f:
                data = json.load(f)
            return tuple(data) if isinstance(data, list) else data
        except Exception as e:
            print(f"⚠️ Failed to load saved region: {e}")
            return None
    return None

def should_ignore_line(line):
    ignored_exact = {"Leader", "Officer", "Members", "Total Fans", "Last Login"}
    line = line.strip()
    return (
        not line or
        line in ignored_exact or
        line.endswith("h ago") or
        line.endswith("m ago") or
        line.endswith("d ago")
    )

def extract_name_fan_pairs_easyocr(image_path):
    img = cv2.imread(image_path)
    results = reader.readtext(img)

    results.sort(key=lambda x: x[0][0][1])  # sort top-to-bottom

    pairs = []
    current_name = None

    def is_fan_count(text):
        return all(c.isdigit() or c == ',' for c in text.replace(' ', ''))

    def is_name(text):
        if should_ignore_line(text):
            return False
        if is_fan_count(text):
            return False
        return True

    for bbox, text, conf in results:
        clean_text = text.strip()
        if conf < 0.4 or not clean_text:
            continue
        if should_ignore_line(clean_text):
            continue

        if current_name is None:
            if is_name(clean_text):
                current_name = clean_text.strip().split(' ')[0]
        else:
            if is_fan_count(clean_text):
                pairs.append((current_name, clean_text))
                current_name = None
            else:
                current_name = None
                if is_name(clean_text):
                    current_name = clean_text.strip().split(' ')[0]

    return pairs

def scroll_and_capture(region, drag_distance=233, duration=0.5):
    x, y, w, h = region
    start_x = int(x + 1.5 * w)
    start_y = int(y + 0.75 * h)
    end_y = start_y - drag_distance

    print(f"⬆️ Scrolling")

    pyautogui.moveTo(start_x, start_y, duration=0.2)
    pyautogui.mouseDown()
    pyautogui.moveTo(start_x, end_y, duration=duration)
    time.sleep(1)
    pyautogui.mouseUp()
    time.sleep(0.5)

    return capture_selected_region(region, verbose=False)

# ---------- MAIN ----------
if __name__ == "__main__":
    focus_umamusume()

    saved_region = load_saved_region()
    if saved_region:
        while True:
            answer = input(f"Do you want to reuse the previously selected region {saved_region}? (y/n): ").strip().lower()
            if answer == "y":
                region_to_use = saved_region
                break
            elif answer == "n":
                region_to_use = select_region()
                break
            else:
                print("Please enter 'y' or 'n'.")
    else:
        region_to_use = select_region()

    all_pairs = []

    image_path = capture_selected_region(region_to_use, verbose=True)
    if image_path:
        last_pairs = extract_name_fan_pairs_easyocr(image_path)

        print("\n📄 Page 1 Results:")
        for name, fans in last_pairs:
            print(f"👤 {name:<15} | 🏁 {fans}")

        all_pairs.extend(last_pairs)

        page_num = 2
        previous_sets = [last_pairs]
        duplicate_limit = 3

        while True:
            image_path = scroll_and_capture(region_to_use)
            if image_path:
                new_pairs = extract_name_fan_pairs_easyocr(image_path)

                print(f"\n📄 Page {page_num} Results:")
                for name, fans in new_pairs:
                    print(f"👤 {name:<15} | 🏁 {fans}")

                all_pairs.extend(new_pairs)

                if new_pairs == previous_sets[-1]:
                    previous_sets.append(new_pairs)
                else:
                    previous_sets = [new_pairs]

                if len(previous_sets) >= duplicate_limit:
                    print("⚠️ Same OCR results detected 3 times. Stopping.")
                    break

                last_pairs = new_pairs
                page_num += 1
            else:
                print("❌ Failed to capture after scroll.")
                break

    # Remove duplicate names
    unique_dict = {}
    for name, fans in all_pairs:
        if name not in unique_dict:
            unique_dict[name] = fans

    # Save to CSV
    csv_filename = "clubTracker.csv"
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Load existing CSV if it exists
    existing_data = {}
    headers = ["Player Name"]

    if os.path.exists(csv_filename):
        with open(csv_filename, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            if rows:
                headers = rows[0]
                for row in rows[1:]:
                    name = row[0]
                    existing_data[name] = row[1:]

    # Filter to keep only date columns (remove gains if leftover from past runs)
    date_headers = [h for h in headers[1:] if len(h) == 10 and h[4] == '-' and h[7] == '-']

    # Add today's date if not already present
    if today_str not in date_headers:
        date_headers.append(today_str)
        date_index = len(date_headers) - 1
    else:
        date_index = date_headers.index(today_str)

    # Update or insert today's fan count
    for name in unique_dict:
        fans = unique_dict[name]
        if name not in existing_data:
            existing_data[name] = [""] * len(date_headers)
        while len(existing_data[name]) < len(date_headers):
            existing_data[name].append("")
        existing_data[name][date_index] = fans

    # Save to CSV with updated headers and data
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Player Name"] + date_headers)
        for name in sorted(existing_data.keys()):
            row = existing_data[name]
            row += [""] * (len(date_headers) - len(row))  # Pad missing
            writer.writerow([name] + row)

    print(f"\n✅ Updated {csv_filename} with raw fan counts under {today_str}.")