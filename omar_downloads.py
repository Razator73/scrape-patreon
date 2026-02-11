#!/usr/bin/env pipenv-shebang
import argparse
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
    logger.info(f'Getting posts for {name}')
    if len([f for f in archive_folder.glob('*')]) == count:
        logger.info('\tNumber of files equal the post count. Skipping')
        return []
    wd.get(url)
    time.sleep(3)
    while load_more := [e for e in wd.find_elements(By.TAG_NAME, "button") if e.text == 'Load more']:
        load_more[0].click()
        time.sleep(5)
    all_links = wd.find_elements(By.TAG_NAME, "a")
    post_links = [(a.text.split('\n')[-1], a.get_property('href')) for a in all_links
                  if a.get_property('href').endswith(f'collection={url.split("/")[-1]}')][::-1]
    logger.info(f'\tFound {len(post_links)}')
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
            logger.info(f'\t{file_name} exists')
            continue
        wd.get(post_link)
        time.sleep(2)
        all_links = wd.find_elements(By.TAG_NAME, "a")
        download_link = [link.get_property('href') for link in all_links
                         if link.get_property('href').startswith(gdrive_url)][0]
        col_posts.append((file_path, download_link))
    return col_posts


def main(logger, show_display):
    download_cols = ['Naruto Shippuden', 'JJK', 'Frieren']

    with Display(visible=show_display) as display:
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
            logger.info(f'Collections:\n{collection_links.keys()}')
            for col in download_cols:
                if col not in collection_links:
                    logger.info(f"Couldn't find the collection: {col}")
                    continue
                collection_links[col]['posts'] = fetch_collection_links(driver, **collection_links[col])
    all_posts = {col['name']: col['posts'] for col in collection_links.values() if 'posts' in col}
    for col, posts in all_posts.items():
        if not posts:
            continue
        logger.info(f'Downloading missing posts for {col}...')
        for post in posts[::-1]:
            gdrive_id = post[1].split('/')[-2]
            down_url = f'https://drive.google.com/uc?id={gdrive_id}'
            retry = True
            retries = 0
            while retry and retries < 5:
                try:
                    logger.info(f'\tDownloading {post[0].name}')
                    gdown.download(down_url, str(post[0]), quiet=True)
                except gdown.exceptions.FileURLRetrievalError:
                    logger.warning(f"Couldn't download {post[0]}")
                    retry = False
                except (BlockingIOError, OSError):
                    retries += 1
                    logger.warning(f'Retrying attempt {retries} for {post[0]}')
                    time.sleep(30)
                else:
                    retry = False


if __name__ == '__main__':
    load_dotenv()
    arg_parser = argparse.ArgumentParser(prog='omar_downloads', description='Scrape Omario Patreon Collections for new videos')
    arg_parser.add_argument('-d', '--show_display', action='store_true', help='Show the display')
    arg_parser.add_argument('-v', '--stout-output', action='store_true', help='Export logging to terminal')
    args = arg_parser.parse_args()

    if args.stout_output:
        file_logger = razator_utils.log.get_stout_logger('omar_downloads', 'INFO')
    else:
        log_file = Path.home() / 'logs' / 'omar_downloads.log'
        log_file.parent.mkdir(exist_ok=True)
        file_logger = razator_utils.log.get_file_logger('omar_downloads', log_file, 'INFO')


    try:
        main(file_logger, args.show_display)
    except Exception:
        if alert_url := os.getenv('DISCORD_ALERT_URL'):
            razator_utils.discord_message(alert_url, 'Omar Download Failed. Check logs for details.')
        file_logger.exception('Omar Download Failed')
        sys.exit(1)