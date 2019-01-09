import sys
import os.path
import requests
from bs4 import BeautifulSoup
# import lxml

s = requests.Session()

recipe_list = []

page_start = 1
page_end = 4
pages = range(page_start, page_end)

headers = requests.utils.default_headers()

headers.update(
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
            }
        )

urlfile = open('recipe_urls.txt', 'w')

for page in pages:
    sys.stdout.write('getting page {} of {}\n'.format(page, page_end - 1))
    sys.stdout.flush()
    results = s.get('https://www.brewtoad.com/recipes?page={}&sort=created_at'.format(page), headers = headers)
    soup = BeautifulSoup(results.text, 'html.parser')
    for recipe in soup.find_all(attrs={"class": "recipe-link"}):
        recipe_list.append(recipe.get('href'))
        urlfile.write('{}\n'.format(recipe.get('href')[9:]))


