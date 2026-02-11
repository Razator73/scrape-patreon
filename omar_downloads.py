#!/usr/bin/env pipenv-shebang
import os
import time
from pathlib import Path

import gdown
import razator_utils
import undetected_chromedriver as uc
from dotenv import load_dotenv
from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By


def remove_part_files(folder):
    folder.mkdir(exist_ok=True)
    for part_file in folder.glob('*.part'):
        part_file.unlink()


def fetch_collection_links(wd, count, name, url):
    download_folder = Path(os.environ['DOWNLOAD_PATH']) / name
    download_folder.mkdir(exist_ok=True)
    archive_folder = Path(os.environ['ARCHIVE_PATH']) / name
    archive_folder.mkdir(exist_ok=True)
    remove_part_files(download_folder)
    remove_part_files(archive_folder)
    print(f'Getting posts for {name}')
    if len([f for f in archive_folder.glob('*')]) == count:
        print('\tNumber of files equal the post count. Skipping')
        return []
    wd.get(url)
    time.sleep(3)
    while load_more := [e for e in wd.find_elements(By.TAG_NAME, "button") if e.text == 'Load more']:
        load_more[0].click()
        time.sleep(5)
    all_links = wd.find_elements(By.TAG_NAME, "a")
    post_links = [(a.text.split('\n')[-1], a.get_property('href')) for a in all_links
                  if a.get_property('href').endswith(f'collection={url.split("/")[-1]}')][::-1]
    print(f'\tFound {len(post_links)}')
    col_posts = []
    gdrive_url = 'https://drive.google.com'
    for i, col_post in enumerate(post_links):
        file_name, post_link = col_post
        file_name = file_name.replace('/', '_').replace('\\', '_')
        file_name = f'{i + 1:03} {file_name}.mp4'
        if file_name == '005 Reacting to One Punch Man S3X4.mp4':
            file_name = '004 Reacting to One Punch Man S3X4.mp4'
        if file_name == '004 Reacting to One Punch Man S3X5.mp4':
            file_name = '005 Reacting to One Punch Man S3X5.mp4'
        file_path = download_folder / file_name
        archive_path = archive_folder / file_name
        if archive_path.exists():
            print(f'\t{file_name} exists')
            continue
        wd.get(post_link)
        time.sleep(2)
        all_links = wd.find_elements(By.TAG_NAME, "a")
        download_link = [link.get_property('href') for link in all_links
                         if link.get_property('href').startswith(gdrive_url)][0]
        col_posts.append((file_path, download_link))
    return col_posts


if __name__ == '__main__':
    load_dotenv()
    download_cols = ['Naruto Shippuden', 'JJK', 'Frieren']

    with Display(visible=False) as display:
        with uc.Chrome(subprocess=True, version_main=razator_utils.get_chrome_major_version()) as driver:
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
            for _ in range(25):
                last_height = driver.execute_script("return document.body.scrollHeight")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
            links = driver.find_elements(By.TAG_NAME, "a")
            collections = [a.find_element(By.XPATH, "../..") for a in links
                           if a.get_property('href').startswith('https://www.patreon.com/collection/')]
            collection_links = {}
            for col in collections:
                col_link = col.find_element(By.TAG_NAME, 'a')
                col_count, col_name = col.text.split('\n')
                collection_links[col_name] = {'name': col_name, 'count': int(col_count),
                                              'url': col_link.get_property('href')}
            print(f'Collections:\n{collection_links.keys()}')
            for col in download_cols:
                if col not in collection_links:
                    print(f"Couldn't find the collection: {col}")
                    continue
                collection_links[col]['posts'] = fetch_collection_links(driver, **collection_links[col])
    all_posts = {col['name']: col['posts'] for col in collection_links.values() if 'posts' in col}
    for col, posts in all_posts.items():
        if not posts:
            continue
        print(f'Downloading missing posts for {col}...')
        for post in posts[::-1]:
            gdrive_id = post[1].split('/')[-2]
            down_url = f'https://drive.google.com/uc?id={gdrive_id}'
            retry = True
            retries = 0
            while retry and retries < 5:
                try:
                    print(f'\tDownloading {post[0].name}')
                    gdown.download(down_url, str(post[0]), quiet=True)
                except gdown.exceptions.FileURLRetrievalError:
                    print(f"Couldn't download {post[0]}")
                    retry = False
                except (BlockingIOError, OSError):
                    retries += 1
                    print(f'Retrying attempt {retries} for {post[0]}')
                    time.sleep(30)
                else:
                    retry = False
