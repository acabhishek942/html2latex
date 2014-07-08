import hashlib
import os
import re
import subprocess
import sys
import uuid

from .webkit2png import webkit2png
from PIL import Image
from django.conf import settings
from django.template.loader import render_to_string
import enchant
from lxml import etree
import redis
import spellchecker
from splinter import Browser


browser = Browser('phantomjs')
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
REGEX_SN = re.compile(r'(?i)\s*(s\s*\.*\s*no\.*|s\s*\.*\s*n\.*)\s*')


def get_image_size(path):
    """ Given the path of the image it gives the size of the image"""
    img = Image.open(path)
    return img.size


def get_image_for_html_table(html, do_spellcheck=False):
    """ Convert HTML table to image to put in latex"""
    html = html.strip()
    if do_spellcheck:
        html = spellchecker.check_spelling_in_html(html)

    wait_time = 0
    root = etree.HTML(html)
    if root.find('.//span[@class="math-tex"]') is not None:
        # mathjax equations present
        wait_time = 5

    td = root.find(".//td")
    if td is not None and td.find('.//span[@class="math-tex"]') is None:
        td_html = etree.tostring(td)
        html = html.replace(td_html, REGEX_SN.sub(" SN ", td_html, 1), 1)

    hashed_html = u"webkit2png-{0}".format(hashlib.sha512(html).hexdigest())

    existing_image_file = redis_client.get(hashed_html)

    if existing_image_file:
        if os.path.isfile(existing_image_file):
            return existing_image_file

    context = {
        "table_inner_html": html,
        "STATIC_ROOT": settings.STATIC_ROOT,
        "MATHAJAX_ROOT": settings.MATHAJAX_ROOT,
    }

    html = render_to_string(
        'web2png-table.html', context)
    unique_id = str(uuid.uuid4())
    html_file = u"/var/tmp/{0}.html".format(unique_id)
    with open(html_file, "wb") as f:
        f.write(html)

    image_file = u"/var/tmp/{0}.png".format(unique_id)
    url = u"file://{0}".format(html_file)

        if wait_time > 0:
            webkit2png(url, image_file, browser=browser, wait_time=wait_time)
    else:
        p = subprocess.Popen(
            ["webkit2png.py", "-o", image_file, html_file])
        p.wait()

    redis_client.set(hashed_html, image_file)

    return image_file
