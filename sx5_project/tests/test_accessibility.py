"""Accessibility the site promises: contrast on the park colours, and the
structure assistive technology relies on. The target is WCAG 2.2 level AAA."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from races.models import Race
from sx5_project.tests.test_results_import import (  # noqa: F401
    plain_static_storage,
    publish,
    season,
    staff,
)

pytestmark = pytest.mark.django_db

CSS = (Path(__file__).parents[1] / "static/css/custom.css").read_text()

NORMAL_TEXT = 7.0  # AAA, text of any size
LARGE_TEXT = 4.5  # AAA, text at least 18.67px bold
LARGE_BOLD_REM = 18.67 / 16

PARKS = [
    "kings-park",
    "linn-park",
    "rouken-glen",
    "pollok-park",
    "bellahouston-park",
    "queens-park",
]


def token(name):
    """A colour token from :root, as (r, g, b)."""
    value = re.search(rf"--sx5-{name}:\s*#([0-9a-f]{{3,6}});", CSS).group(1)
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def park_pair(slug):
    """The colour a park fills with and the ink it puts on top."""
    rule = re.search(rf"\.park-{slug}\s*{{([^}}]*)}}", CSS).group(1)
    fill = re.search(r"--park:\s*var\(--sx5-(\w+)\)", rule).group(1)
    ink = re.search(r"--park-ink:\s*var\(--sx5-(\w+)\)", rule).group(1)
    return token(fill), token(ink)


@pytest.mark.parametrize("slug", PARKS)
def test_text_on_a_park_colour_can_be_read(slug):
    fill, ink = park_pair(slug)
    assert contrast(fill, ink) >= LARGE_TEXT


def test_text_on_a_park_colour_is_large_enough_for_that_contrast():
    # Red and blue only reach the large-text ratio, so text on colour is large.
    size = float(re.search(r"--sx5-on-colour:\s*([\d.]+)rem;", CSS).group(1))
    assert size >= LARGE_BOLD_REM
    for selector in (".band__meta,\n.band__desc", ".band__tab", ".filter-btn"):
        rule = CSS[CSS.index(selector + " {") :].split("}")[0]
        assert "font-size: var(--sx5-on-colour)" in rule
        assert "font-weight: 700" in rule


@pytest.mark.parametrize("slug", ["linn-park", "rouken-glen", "pollok-park", "queens-park"])
def test_four_parks_take_text_of_any_size(slug):
    fill, ink = park_pair(slug)
    assert contrast(fill, ink) >= NORMAL_TEXT


@pytest.mark.parametrize("paper", ["cream", "sand"])
def test_body_text_and_links_reach_seven_to_one(paper):
    assert contrast(token("black"), token(paper)) >= NORMAL_TEXT
    assert contrast(token("purple"), token(paper)) >= NORMAL_TEXT


def page(client, url):
    response = client.get(url)
    assert response.status_code == 200
    return response.content.decode()


@pytest.fixture
def race(season, staff):  # noqa: F811
    publish(season, staff)
    return Race.objects.get(name="King's Park")


def test_the_skip_link_comes_first_and_lands_on_main(client, race):
    html = page(client, race.get_absolute_url())
    body = html[html.index("<body>") :]
    assert body.split("<a ", 1)[1].startswith('class="skip-link" href="#main"')
    assert '<main id="main" tabindex="-1">' in html


def test_the_page_heading_is_inside_main(client, race):
    for url in (race.get_absolute_url(), reverse("info:contact")):
        html = page(client, url)
        assert html.count("<h1") == 1
        assert html.index("<main") < html.index("<h1") < html.index("</main>")


def test_the_title_says_which_view_of_the_race_it_is(client, race):
    results = page(client, race.get_absolute_url())
    standings = page(client, race.get_absolute_url() + "?tab=classification-results")
    assert "<title>King&#x27;s Park race results 2026/2027, South by Five</title>" in results
    assert (
        "<title>Series standings after King&#x27;s Park 2026/2027, South by Five</title>"
        in standings
    )


def test_filters_say_whether_they_are_pressed(client, race):
    for tab in ("race-results", "classification-results"):
        html = page(client, race.get_absolute_url() + "?tab=" + tab)
        assert html.count('class="filter-btn filter-btn-male" aria-pressed="false"') == 1
        assert html.count('aria-pressed="false"') == 3
        assert 'role="status"' in html


def test_the_results_table_can_be_scrolled_from_the_keyboard(client, race):
    html = page(client, race.get_absolute_url())
    assert '<div class="table-responsive" tabindex="0" role="region" aria-label=' in html


def test_no_link_opens_a_new_tab_unannounced(client, race):
    for url in (race.get_absolute_url(), reverse("info:contact"), reverse("info:developer")):
        assert 'target="_blank"' not in page(client, url)


def test_a_park_without_results_is_not_a_dead_link(client, race):
    html = page(client, reverse("info:contact"))
    nav = html[html.index("site-nav__parks") : html.index("site-nav__right")]
    assert 'href="#"' not in nav
    assert "no results yet" in nav


def test_the_info_page_explains_the_codes_the_results_use(client, race):
    html = page(client, reverse("info:contact"))
    assert 'id="key"' in html
    assert '<abbr title="Did not finish">DNF</abbr>' in html
    assert reverse("info:contact") + "#key" in page(client, race.get_absolute_url())
