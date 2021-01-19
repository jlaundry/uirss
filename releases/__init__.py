
import logging
import requests
import json
from datetime import datetime
from xml.dom import minidom
from urllib import parse
from email import utils

from xml.etree.ElementTree import Element, SubElement, Comment, tostring, register_namespace

import azure.functions as func

XMLNS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}

REQ_URL = 'https://community.svc.ui.com/'
REQ_DATA = {
    "operationName": "GetReleases",
    "variables": {
        "limit": 50,
        "offset": 0,
        "sortBy": "LATEST",
        "tags": [
            "edgemax",
            "unifi-wireless"
        ],
        "betas": [],
        "alphas": [],
        "featuredOnly": True
    },
    "query": "query GetReleases($limit: Int, $offset: Int, $productFamily: String, $products: [String!], $searchTerm: String, $sortBy: ReleasesSortBy, $stage: ReleaseStage, $statuses: [ReleaseStatus!], $tagMatchType: TagMatchType, $tags: [String!], $betas: [String!], $alphas: [String!], $type: ReleaseType, $featuredOnly: Boolean, $nonFeaturedOnly: Boolean) {\n  releases(limit: $limit, offset: $offset, productFamily: $productFamily, products: $products, searchTerm: $searchTerm, sortBy: $sortBy, stage: $stage, statuses: $statuses, tagMatchType: $tagMatchType, tags: $tags, betas: $betas, alphas: $alphas, type: $type, featuredOnly: $featuredOnly, nonFeaturedOnly: $nonFeaturedOnly) {\n    items {\n      ...BasicRelease\n      __typename\n    }\n    pageInfo {\n      limit\n      offset\n      __typename\n    }\n    totalCount\n    __typename\n  }\n}\n\nfragment BasicRelease on Release {\n  id\n  slug\n  type\n  title\n  version\n  stage\n  tags\n  betas\n  alphas\n  isFeatured\n  isLocked\n  stats {\n    comments\n    views\n    __typename\n  }\n  createdAt\n  lastActivityAt\n  updatedAt\n  userStatus {\n    ...UserStatus\n    __typename\n  }\n  __typename\n}\n\nfragment UserStatus on UserStatus {\n  isFollowing\n  lastViewedAt\n  reported\n  vote\n  __typename\n}\n"
}

REQ_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://community.ui.com",
    "Referer": "https://community.ui.com/releases",
    "TE": "Trailers",
}

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # for k, v in XMLNS.iteritems():
    #     register_namespace(k, v)

    doc = Element('rss')
    doc.set('version', '2.0')

    channel = SubElement(doc, 'channel')
    title = SubElement(channel, 'title')
    link = SubElement(channel, 'link')
    description = SubElement(channel, 'description')

    title.text = "Ubiquiti Releases"
    link.text = "http://localhost:7071/api/releases"
    description.text = "Ubiquiti Releases"

    r = requests.post(REQ_URL, json=REQ_DATA, headers=REQ_HEADERS)
    # logging.debug(f"status_code:{r.status_code}, text:{r.text}")
    # logging.debug(json.dumps(r.json(), indent=2))
    
    for item in r.json()['data']['releases']['items']:
        i = SubElement(channel, 'item')
        title = SubElement(i, 'title')
        link = SubElement(i, 'link')
        guid = SubElement(i, 'guid')
        pubDate = SubElement(i, 'pubDate')

        title.text = f"{item['title']} - {item['version']} ({item['stage']})"
        link.text = f"https://community.ui.com/releases/{item['slug']}/{item['id']}"
        guid.text = item['id']
        createdAt = datetime.strptime(item['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ")
        pubDate.text = utils.formatdate(createdAt.timestamp())
        
        for tag in item['tags']:
            category = SubElement(i, 'category')
            category.text = tag

        description = SubElement(i, 'description')
        description.text = json.dumps(item, indent=2)

    return func.HttpResponse(
        tostring(doc),
        mimetype="text/xml",
    )
