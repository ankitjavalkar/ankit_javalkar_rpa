import csv
import datetime
import logging
import re
import requests
import shutil
import os

from robocorp.tasks import task

from selenium import webdriver
from selenium.webdriver import FirefoxOptions

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException


logger = logging.getLogger()


opts = FirefoxOptions()
opts.add_argument("--headless")
driver = webdriver.Firefox(options=opts)
wait = WebDriverWait(driver, 60)


DURATION = 0
SECTION = ""
QUERY = "police"
URL = "https://www.reuters.com/"

@task
def gather_news_task():
    driver.get(URL)
    run_search_query(driver, QUERY)

    data_row = []
    articles_are_in_date_range = True
    while articles_are_in_date_range:

        # get all articles on page
        article_elems = wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, '//div[contains(@class, "search-results__sectionContainer")]//div[@data-testid="BasicCard"]')
            )
        )

        print(f"Number of articles found on page: {len(article_elems)}")
        logger.info(f"Number of articles found on page: {len(article_elems)}")

        # Iterate over every article in the page
        for elem in article_elems:
            # Article timestamp
            elem_time = elem.find_element(By.CSS_SELECTOR, "time").get_attribute("datetime")

            # Articles are arranged by latest first. First article not in datetime range, breaks the loop
            if not article_date_in_range(elem_time, DURATION):
                articles_are_in_date_range = False
                logger.info(f"Articles are no longer in the given date time range")
                break

            # Article title
            elem_title = elem.find_element(By.CSS_SELECTOR, "header a span").text

            # Fetch the image if present, download and save locally
            try:
                elem_image_url = elem.find_element(By.CSS_SELECTOR, 'a[data-testid="Link"] img').get_attribute("src")
                logger.debug(f"Image found. Image URL: {elem_image_url}")
                local_path = download_file(elem_image_url)
                logger.debug(f"Image downloaded. Image path: {local_path}")
            except NoSuchElementException:
                elem_image_url = ''
                local_path = ''
                logger.debug(f"Image not found for article with title: {elem_title}")

            # Find the number occurences of search query in title
            query_count_in_title = get_query_count_in_title(elem_title, QUERY)
            # Find currency amount in title
            amount_in_title = parse_amount_in_title(elem_title)

            data_row.append(
                {
                    'title': elem_title,
                    'time': elem_time,
                    'image_url': elem_image_url,
                    'image_path': local_path,
                    'currncy_amount_in_title': amount_in_title,
                    'query_count': query_count_in_title,
                }
            )
            print(f"Data rrr: {elem_title} ==== {elem_time} ===== {elem_image_url} ===== {local_path}")

        # Hit pagination next
        try:
            wait.until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, 'svg[data-testid="SvgChevronRight"]')
                )
            ).click()
            logger.info("Moving to next page in pagination link")
        except:
            logger.error("Unable to click next pagination")


    driver.quit()

    # Save output to CSV file
    save_output_to_csv(data_row)


def click_search_button(driver):
    wait.until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, 'svg[data-testid="SvgSearch"]')
        )
    ).click()

def run_search_query(driver, query):
    click_search_button(driver)
    wait.until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, 'input[data-testid="FormField:input"')
        )
    ).send_keys(query + u'\ue007')

def get_time_duration(duration_id):
    duration = duration_id if duration_id == 0 else duration_id - 1
    today_dt = datetime.datetime.today()
    curr_month = today_dt.month
    curr_year = today_dt.year

    from_year = curr_year + (curr_month - duration - 1) // 12
    from_month = (curr_month - duration - 1) % 12 + 1

    from_dt = datetime.datetime(from_year, from_month, 1, 0, 0, 0, 0)

    return from_dt

def download_file(url):
    local_filename = url.split('/')[-1]
    local_path = "output"
    full_file_path = os.path.join(local_path, local_filename)
    with requests.get(url, stream=True) as r:
        with open(full_file_path, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    return full_file_path

def article_date_in_range(article_datetime, duration):
    timestamp_pattern = "%Y-%m-%dT%H:%M:%S" # Example: 2024-05-19T05:29:22Z

    article_datetime = article_datetime.rsplit('.', 1)[0].strip('Z')

    article_dt_obj = datetime.datetime.strptime(article_datetime, timestamp_pattern)
    from_dt = get_time_duration(duration)

    if from_dt <= article_dt_obj <= datetime.datetime.today():
        return True

    return False


def get_query_count_in_title(title, query):
    words = title.split(' ')
    count = 0
    for wd in words:
        if wd.lower == query:
            count += 1

    return count

def parse_amount_in_title(title):
    regex_identifiers = [
        "\d+[\,\.]*\d* dollars"
        "\$\d+[\,\.]*\d*"
        "\d+[\,\.]*\d* USD"
    ]

    for rx in regex_identifiers:
        if re.search(rx, title):
            return True

    return False

def save_output_to_csv(data):
    keys = data[0].keys()

    with open('output/output.csv', 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
