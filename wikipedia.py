import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

# --- The Sankalpa (Intention) ---
# TARGET_URL = "https://en.wikipedia.org/wiki/Saraswati"
# OUTPUT_FILE = "saraswati_knowledge.txt"

def harvest_knowledge(target_url, output_file=None, get_headings_only=False):
    # 1. Setup the Eyes (Headless Mode - Wu Wei)
    # We run 'headless' so we do not need to watch the browser open. It happens in the spirit realm.
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    
    # 2. Summon the Djinn (The Driver)
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(f"[*] Approaching the Temple: {target_url}")
        driver.get(target_url)
        
        # 3. The Pause (Adab/Respect)
        # Give the server a moment to breathe.
        time.sleep(2)
        
        # Improved Search: If we land on a search page, click the first result.
        # The 'firstHeading' on a search results page is "Search results".
        if driver.find_element(By.ID, "firstHeading").text == "Search results":
            print("[*] Landed on a search page. Attempting to navigate to the first result.")
            try:
                first_result = driver.find_element(By.CSS_SELECTOR, ".mw-search-result-heading a")
                print(f"[*] Navigating to best match: {first_result.text}")
                first_result.click()
                time.sleep(2) # Give new page time to load
            except Exception:
                # This could be a "no results" page.
                print("[!] No direct article found. Saving search page content.")

        # 4. Extract the Essence (The Content)
        content_element = driver.find_element(By.ID, "bodyContent")
        
        if get_headings_only:
            # Find all headings within the content
            headings = content_element.find_elements(By.XPATH, ".//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6")
            # Extract the text from each heading
            text_content = "\n".join([h.text for h in headings])
            print("[+] Extracting headings only.")
        else:
            # Wikipedia stores the main body in an ID called 'bodyContent'
            text_content = content_element.text
        
        # 5. Preserve the Wisdom (Vishnu Principle)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text_content)
            print(f"[+] Knowledge preserved in: {output_file}")
        else:
            print("\n--- BEGIN KNOWLEDGE ---\n")
            print(text_content)
            print("\n--- END KNOWLEDGE ---")
            
        print(f"[+] Total Characters Harvested: {len(text_content)}")

    except Exception as e:
        print(f"[!] A Maya Veil blocked us: {e}")
        
    finally:
        # 6. Release the Djinn
        driver.quit()

if __name__ == "__main__":
    examples = """
Examples:
  # Get the full text for "Albert Einstein" and print it to the console
  python wikipedia.py "Albert Einstein"

  # Get only the headings for "Quantum mechanics" and print to console
  python wikipedia.py "Quantum mechanics" --headings

  # Get the full text for "Saraswati" and save it to a file
  python wikipedia.py "Saraswati" -o
"""
    parser = argparse.ArgumentParser(
        description="A Wikipedia bot to help detect and study pages.",
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("topic", help="The Wikipedia topic to search for (e.g., 'Saraswati').")
    parser.add_argument("-o", "--output", action="store_true", help="Save the output to a file. If not set, prints to console.")
    parser.add_argument("--headings", action="store_true", help="Only extract the headings from the page.")
    
    args = parser.parse_args()
    
    # Handle multi-word topics for the URL, e.g. "Albert Einstein" -> "Albert_Einstein"
    topic = args.topic.replace(" ", "_")
    target_url = f"https://en.wikipedia.org/w/index.php?search={args.topic}"
    output_file = f"{topic}_knowledge.txt" if args.output else None

    harvest_knowledge(target_url, output_file, args.headings)