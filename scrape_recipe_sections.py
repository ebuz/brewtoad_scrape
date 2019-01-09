import sys
import pathlib
import os
import os.path
import shutil
import argparse
import re
import csv
import glob
import requests
from bs4 import BeautifulSoup
# import lxml

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--step_by', type=int, default = 1)
parser.add_argument('--skip', type=int, default = 0)
parser.add_argument('--urls', default = 'recipe_urls.txt')

args = parser.parse_args()

requester = requests.Session()
headers = requests.utils.default_headers()
headers.update(
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
            }
        )


def safe_request(url):
    result = None
    try:
        result = requester.get(url, headers = headers)
    except Exception as e:
        sys.stderr.write('Failed get of url {} ({})\n'.format(url, e))
    return result

def extract_variants(ancestor_page, full_page = False):
    if full_page:
        soup = BeautifulSoup(ancestor_page, 'html.parser')
        soup = soup.find(attrs = {"class": "ancestry-list"})
        if not soup:
            return []
    else:
        soup = BeautifulSoup(ancestor_page, 'html.parser')
    def recipe_href(href):
        return href and re.compile("^/recipes/.*").search(href)
    return [variant_a.get('href')[9:] for variant_a in soup.find_all(href = recipe_href)]

comment_fields = ['commentId', 'brewerId', 'brewerName', 'date', 'comment', 'replyIds']

def parse_comment(comment):
    parsed_comment = {}
    parsed_comment['commentId'] = comment.get('id')[15:]
    parsed_comment['brewerId'] = comment.div.div.a.get('href')[7:]
    parsed_comment['brewerName'] = comment.div.div.a.text.strip()
    parsed_comment['date'] = comment.div.div.small.text.strip()
    parsed_comment['comment'] = comment.find(attrs = {"class": "recipe-comment-body"}).text.strip()
    parsed_comment['replyIds'] = [c.get('id')[15:] for c in comment.ol.find_all('li', recursive = False)]
    return parsed_comment

def extract_comments(page):
    soup = BeautifulSoup(page, 'html.parser')
    comments = soup.find_all(attrs = {"class": "recipe-comment"})
    return [parse_comment(comment) for comment in comments]

# log_fields = ['brewerId', 'brewerName', 'date', 'brewingNotes', 'mashTime', 'strikeTemperature', 'mashChecks', 'boilTime', 'preBoilVolume', 'postBoilVolume', 'evaporationRate', 'volumeInFermenter', 'measuredOriginalGravity', 'fermentationChecks', 'volumeBottled', 'primingSugar', 'primingSugarAmount', 'agingTime', 'tasteRating', 'tasteNotes']

# def extract_logs(page):
#     soup = BeautifulSoup(page, 'html.parser')
#     log = soup.find(attrs = {"class": "subnav--content"})
#     return log

def error_page(page):
    soup = BeautifulSoup(page, 'html.parser')
    return soup.find(attrs = {"class": "site-container errors errors-error"})

def brew_log_href(href):
    return href and re.compile(".*/brew-logs/.*").search(href)

def skip_and_step(items, skip = 0, step_by = 1):
    for i, item in enumerate(items):
        if i < skip:
            continue
        elif (i - skip) % step_by != 0:
            continue
        else:
            yield item
    return

brew_toad_prefix = 'https://www.brewtoad.com/recipes/'

for recipe in skip_and_step(open(args.urls, 'r'), args.skip, args.step_by):
    recipe = recipe.strip()
    sys.stdout.write('Working on recipe {}\n'.format(recipe))
    recipe_page = safe_request('{}{}'.format(brew_toad_prefix, recipe))
    if recipe_page is not None and (recipe_page.status_code is 404 or error_page(recipe_page.text)):
        sys.stdout.write('    recipe deleted, moving on\n')
        continue
    os.makedirs('recipes/{}'.format(recipe), exist_ok = True)
    if recipe_page is not None:
        sys.stdout.write('    finding comments')
        comments = extract_comments(recipe_page.text)
        if os.path.isfile('recipes/{}/comments.csv'.format(recipe)):
            sys.stdout.write('...already saved\n')
        else:
            if len(comments) > 0:
                sys.stdout.write('...saved\n')
                with open('recipes/{}/comments.csv'.format(recipe), 'w') as comment_file:
                    comment_writer = csv.DictWriter(comment_file, fieldnames = comment_fields)
                    comment_writer.writeheader()
                    comment_writer.writerows(comments)
    else:
        sys.stdout.write('    http error for recipe\n')
    sys.stdout.write('    saving recipe')
    if os.path.isfile('recipes/{}/recipe.xml'.format(recipe)):
        sys.stdout.write('...already saved\n')
    else:
        recipe_xml = safe_request('{}{}.xml'.format(brew_toad_prefix, recipe))
        if recipe_xml is None:
            sys.stdout.write('    http error for recipe xml\n')
        else:
            with open('recipes/{}/recipe.xml'.format(recipe), 'w') as recipe_file:
                recipe_file.write(recipe_xml.text)
                sys.stdout.write('...saved\n')
    sys.stdout.write('    finding variants')
    recipe_variant_page = safe_request('{}{}/ancestry'.format(brew_toad_prefix, recipe))
    if recipe_variant_page is None:
        sys.stdout.write('    http error getting variants\n')
    else:
        variants = extract_variants(recipe_variant_page.text, full_page = True)
        if os.path.isfile('recipes/{}/variants.txt'.format(recipe)):
            sys.stdout.write('...already saved\n')
        else:
            if len(variants) > 0:
                with open('recipes/{}/variants.txt'.format(recipe), 'w') as variant_file:
                    variant_file.write('\n'.join(variants))
                    sys.stdout.write('...saved\n')
    sys.stdout.write('    finding logs\n')
    recipe_logs = safe_request('{}{}/brew-logs'.format(brew_toad_prefix, recipe))
    if recipe_logs is None:
        sys.stdout.write('    http error for recipe logs\n')
    else:
        recipe_logs_soup = BeautifulSoup(recipe_logs.text, 'html.parser')
        for log_a in recipe_logs_soup.find_all(href = brew_log_href):
            sys.stdout.write('    checking log {}'.format(log_a.get('href')))
            if os.path.isfile('{}.html'.format(log_a.get('href'))):
                sys.stdout.write('...already saved\n')
                continue
            recipe_log = safe_request('https://www.brewtoad.com{}'.format(log_a.get('href')))
            if recipe_log is None:
                sys.stdout.write('...http error for recipe log\n')
            else:
                log_save_location = pathlib.Path('.{}.html'.format(log_a.get('href')))
                os.makedirs(str(log_save_location.parent), exist_ok = True)
                with open(str(log_save_location), 'w') as log_file:
                    log_file.write(recipe_log.text)
                    sys.stdout.write('...saved\n')


