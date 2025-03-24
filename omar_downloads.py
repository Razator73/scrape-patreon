import os
import time
from pathlib import Path

import gdown
import undetected_chromedriver as uc
from dotenv import load_dotenv
from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By


def fetch_collection_links(wd, count, name, url):
    download_folder = Path(os.environ['DOWNLOAD_PATH']) / name
    download_folder.mkdir(exist_ok=True)
    for part_file in download_folder.glob('*.part'):
        part_file.unlink()
    print(f'Getting posts for {name}')
    if len([f for f in download_folder.glob('*')]) == count:
        print('\tNumber of files equal the post count. Skipping')
        return []
    wd.get(url)
    time.sleep(3)
    while load_more := [e for e in wd.find_elements(By.XPATH, "//div[contains(@class, 'sc-eCImPb cXvBBE')]")
                        if e.text == 'Load more']:
        load_more[0].click()
        time.sleep(5)
    post_divs = wd.find_elements(By.XPATH, "//div[contains(@data-tag, 'post-card')]")[::-1]
    print(f'\tFound {len(post_divs)}')
    col_posts = []
    for i, col_post in enumerate(post_divs):
        file_name, download_link = col_post.text.split('\n')[:2]
        file_name = f'{i + 1:03} {file_name}'
        col_posts.append((download_folder / file_name, download_link))
    return col_posts


if __name__ == '__main__':
    load_dotenv()
    download_cols = ['Dragonball', 'Breaking Bad', 'Solo Leveling', 'NARUTO REACTIONS']

    with Display(visible=False) as display:
        with uc.Chrome(subprocess=True) as driver:
            driver.get('https://www.patreon.com/login')
            time.sleep(3)
            email_element = driver.find_element(By.NAME, 'email')
            email_element.send_keys(os.environ['PATREON_USERNAME'])
            email_element.submit()
            time.sleep(1)
            driver.find_element(By.NAME, 'current-password').send_keys(os.environ['PATREON_PASSWORD'])
            email_element.submit()
            time.sleep(2)
            driver.get('https://www.patreon.com/c/omariorpg/collections')
            time.sleep(10)
            collections = driver.find_elements(By.XPATH, "//div[contains(@class, 'sc-ieecCq hlVSeb')]")
            collection_links = {}
            for col in collections:
                col_link = col.find_element(By.TAG_NAME, 'a')
                col_count, col_name = col.text.split('\n')
                collection_links[col_name] = {'name': col_name, 'count': int(col_count),
                                              'url': col_link.get_property('href')}
            for col in download_cols:
                if col not in collection_links:
                    print(f"Couldn't find the collection: {col}")
                    continue
                collection_links[col]['posts'] = fetch_collection_links(driver, **collection_links[col])
    all_posts = {col['name']: col['posts'] for col in collection_links.values() if 'posts' in col}
    for col, posts in all_posts.items():
        print(f'Downloading missing posts for {col}...')
        for post in posts[::-1]:
            if post[0].exists():
                print(f'{post[0].name} exists')
                continue
            gdrive_id = post[1].split('/')[-2]
            down_url = f'https://drive.google.com/uc?id={gdrive_id}'
            # print(f'\tDownloading {post[0].name}')
            retry = True
            retries = 0
            while retry and retries < 5:
                try:
                    gdown.download(down_url, str(post[0]), quiet=False)
                except gdown.exceptions.FileURLRetrievalError:
                    print(f"Couldn't download {post[0]}")
                    retry = False
                except (BlockingIOError, OSError):
                    retries += 1
                    print(f'Retrying attempt {retries} for {post[0]}')
                    time.sleep(30)
                else:
                    retry = False
