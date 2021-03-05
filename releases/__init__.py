
import copy
import logging
import requests
import json
from datetime import datetime, timezone
from urllib import parse
from email import utils

# Must use lxml, because xml.etree doesn't support CDATA
# from xml.etree.ElementTree import Element, SubElement, Comment, tostring, register_namespace
from lxml.etree import Element, SubElement, Comment, CDATA, tostring, register_namespace

import azure.functions as func

XMLNS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    # "media": "http://search.yahoo.com/mrss/",
    "sy": "http://purl.org/rss/1.0/modules/syndication/",
}

SELF_URL = "https://jlaundry-uirss.azurewebsites.net/api/releases"

REQ_URL = 'https://community.svc.ui.com/'
REQ_RELEASE_DATA = {
    "operationName": "GetReleases",
    "variables": {
        "limit": 50,
        "offset": 0,
        "sortBy": "LATEST",
        "tags": [
            "edgemax",
            "unifi",
        ],
        "betas": [],
        "alphas": [],
        "featuredOnly": True
    },
    "query": "query GetReleases($limit: Int, $offset: Int, $productFamily: String, $products: [String!], $searchTerm: String, $sortBy: ReleasesSortBy, $stage: ReleaseStage, $statuses: [ReleaseStatus!], $tagMatchType: TagMatchType, $tags: [String!], $betas: [String!], $alphas: [String!], $type: ReleaseType, $featuredOnly: Boolean, $nonFeaturedOnly: Boolean) {\n  releases(limit: $limit, offset: $offset, productFamily: $productFamily, products: $products, searchTerm: $searchTerm, sortBy: $sortBy, stage: $stage, statuses: $statuses, tagMatchType: $tagMatchType, tags: $tags, betas: $betas, alphas: $alphas, type: $type, featuredOnly: $featuredOnly, nonFeaturedOnly: $nonFeaturedOnly) {\n    items {\n      ...BasicRelease\n      __typename\n    }\n    pageInfo {\n      limit\n      offset\n      __typename\n    }\n    totalCount\n    __typename\n  }\n}\n\nfragment BasicRelease on Release {\n  id\n  slug\n  type\n  title\n  version\n  stage\n  tags\n  betas\n  alphas\n  isFeatured\n  isLocked\n  stats {\n    comments\n    views\n    __typename\n  }\n  createdAt\n  lastActivityAt\n  updatedAt\n  userStatus {\n    ...UserStatus\n    __typename\n  }\n  __typename\n}\n\nfragment UserStatus on UserStatus {\n  isFollowing\n  lastViewedAt\n  reported\n  vote\n  __typename\n}\n"
}

REQ_RELEASE_INFO = {
    "operationName":"GetRelease",
    "variables": {
        # "id":"8d3b98e1-b9d4-4ab3-b8da-721dbe9ab842"
    },
    "query": "query GetRelease($id: ID!) {\n  release(id: $id) {\n    ...Release\n    __typename\n  }\n}\n\nfragment Release on Release {\n  ...BasicRelease\n  groupId\n  content {\n    ...Content\n    __typename\n  }\n  newFeatures {\n    ...Content\n    __typename\n  }\n  improvements {\n    ...Content\n    __typename\n  }\n  bugfixes {\n    ...Content\n    __typename\n  }\n  knownIssues {\n    ...Content\n    __typename\n  }\n  importantNotes {\n    ...Content\n    __typename\n  }\n  instructions {\n    ...Content\n    __typename\n  }\n  products {\n    id\n    title\n    description\n    image\n    storeUrl\n    quantity\n    __typename\n  }\n  links {\n    url\n    title\n    checksums {\n      md5\n      sha256\n      __typename\n    }\n    __typename\n  }\n  editor {\n    ...UserWithStats\n    __typename\n  }\n  status\n  author {\n    ...UserWithStats\n    __typename\n  }\n  publishedAs {\n    ...User\n    __typename\n  }\n  __typename\n}\n\nfragment BasicRelease on Release {\n  id\n  slug\n  type\n  title\n  version\n  stage\n  tags\n  betas\n  alphas\n  isFeatured\n  isLocked\n  stats {\n    comments\n    views\n    __typename\n  }\n  createdAt\n  lastActivityAt\n  updatedAt\n  userStatus {\n    ...UserStatus\n    __typename\n  }\n  __typename\n}\n\nfragment UserStatus on UserStatus {\n  isFollowing\n  lastViewedAt\n  reported\n  vote\n  __typename\n}\n\nfragment Content on Content {\n  type\n  ... on TextContent {\n    content\n    __typename\n  }\n  ... on ImagesContent {\n    grid {\n      images {\n        src\n        caption\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  ... on VideoContent {\n    src\n    __typename\n  }\n  ... on AttachmentsContent {\n    files {\n      filename\n      url\n      isPublic\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment UserWithStats on User {\n  ...User\n  stats {\n    questions\n    answers\n    solutions\n    comments\n    stories\n    score\n    __typename\n  }\n  __typename\n}\n\nfragment User on User {\n  id\n  username\n  title\n  slug\n  avatar {\n    color\n    content\n    image\n    __typename\n  }\n  isEmployee\n  registeredAt\n  lastOnlineAt\n  groups\n  showOfficialBadge\n  canBeMentioned\n  canViewProfile\n  canStartConversationWith\n  __typename\n}\n"
}

REQ_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://community.ui.com",
    "Referer": "https://community.ui.com/releases",
    "TE": "Trailers",
}

RELEASE_INFO_SECTIONS = [
    ("New Features", "newFeatures"),
    ("Improvements", "improvements"),
    ("Bug Fixes", "bugfixes"),
    ("Known Issues", "knownIssues"),
]

def main(req: func.HttpRequest, outfile: func.Out[func.InputStream]) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # for k, v in XMLNS.iteritems():
    #     register_namespace(k, v)

    doc = Element('rss', nsmap=XMLNS)
    doc.set('version', '2.0')

    channel = SubElement(doc, 'channel')
    title = SubElement(channel, 'title')
    atomlink = SubElement(channel, f"{{{XMLNS['atom']}}}link")
    link = SubElement(channel, 'link')
    description = SubElement(channel, 'description')
    lastBuildDate = SubElement(channel, "lastBuildDate")
    updatePeriod = SubElement(channel, f"{{{XMLNS['sy']}}}updatePeriod")
    updateFrequency = SubElement(channel, f"{{{XMLNS['sy']}}}updateFrequency")

    title.text = "Ubiquiti Releases"
    link.text = SELF_URL
    atomlink.set('href', SELF_URL)
    atomlink.set('rel', 'self')
    atomlink.set('type', 'application/rss+xml')
    description.text = "Ubiquiti Releases - Featured updates tagged edgemax and/or unifi"
    lastBuildDate.text = utils.formatdate(datetime.now(timezone.utc).timestamp())
    updatePeriod.text = "hourly"
    updateFrequency.text = "1"

    session = requests.Session()

    r = session.post(REQ_URL, json=REQ_RELEASE_DATA, headers=REQ_HEADERS)
    # logging.debug(f"status_code:{r.status_code}, text:{r.text}")
    # logging.debug(json.dumps(r.json(), indent=2))

    for item in r.json()['data']['releases']['items']:
        node = SubElement(channel, 'item')
        title = SubElement(node, 'title')
        creator = SubElement(node, f"{{{XMLNS['dc']}}}creator")
        link = SubElement(node, 'link')
        guid = SubElement(node, 'guid')
        pubDate = SubElement(node, 'pubDate')
        description = SubElement(node, 'description')

        title.text = f"{item['title']} - {item['version']} ({item['stage']})"
        link.text = f"https://community.ui.com/releases/{item['slug']}/{item['id']}"
        guid.text = f"https://community.ui.com/releases/{item['slug']}/{item['id']}"
        createdAt = datetime.strptime(item['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ")
        pubDate.text = utils.formatdate(createdAt.timestamp())

        for tag in item['tags']:
            category = SubElement(node, 'category')
            category.text = CDATA(tag)

        release_info_query = copy.deepcopy(REQ_RELEASE_INFO)
        release_info_query['variables']['id'] = item['id']
        release_info = session.post(REQ_URL, json=release_info_query, headers=REQ_HEADERS)
        release_info = release_info.json()['data']['release']

        creator.text = CDATA(release_info['publishedAs']['username'])

        page = ""

        for (h1, section) in RELEASE_INFO_SECTIONS:
            logging.warning(json.dumps(release_info[section], indent=2))
            if release_info[section] is None:
                continue
            content = "\n".join([x['content'] for x in release_info[section] if x['type'] == 'TEXT' and len(x['content']) > 0])
            page += f"<h1>{h1}</h1><br />{content}"

        # page += "<h1>Products</h1><ul>"
        # for product in release_info['products']:
        #     page += f"<li>{product['title']}</li>"
        # page += "</ul>"

        description.text = CDATA(page)

    output = tostring(doc, pretty_print=True, encoding='UTF-8', xml_declaration=True)
    outfile.set(output)

    return func.HttpResponse(
        output,
        mimetype="text/xml",
    )
