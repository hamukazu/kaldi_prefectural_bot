import json
import re
import os
from datetime import datetime, timezone, timedelta
import datastore
from tiny_bsky import Client
from mastodon import Mastodon


def show(d, pref, pref_en):
    header = f"{pref}カルディセール情報\n\n"
    footer_url = f"https://hamukazu.github.io/kaldi_sale_info/#{pref_en}"
    s = header
    if len(d) == 0:
        url_start = None
        url_end = None
        footer_url = None
        s += f"{pref}のセール情報は現在ございません。"
    else:
        for x in d:
            s += x["shop"]
            s += "："
            s += x["title"]
            s += "\n"
            s += "  "
            if x["include_now"]:
                s += "【現在開催中】"
            s += x["date"]
            s += "\n"
        s += "\n"
        url_start = len(s.encode("utf-8"))
        s += footer_url
        url_end = len(s.encode("utf-8"))
    return s, url_start, url_end, footer_url


def include_now(now, strdate_from, strdate_to):
    datetime_from = datetime.fromisoformat(strdate_from + "+09:00")
    datetime_to = datetime.fromisoformat(strdate_to + "+09:00") + timedelta(hours=21)
    return now >= datetime_from and now <= datetime_to


def lambda_handler(event, context):
    pref = os.environ["PREF"]
    pref_en = os.environ["PREF_EN"]
    bsky_user = os.environ["BSKY_USER"]
    bsky_password = os.environ["BSKY_PASSWORD"]
    mstdn_api_base_url = os.environ["MSTDN_API_BASE_URL"]
    mstdn_access_token = os.environ["MSTDN_ACCESS_TOKEN"]
    dry_run = int(os.environ.get("DRY_RUN", 0))
    no_save = int(os.environ.get("NO_SAVE", 0))

    store = datastore.store("pref_sale.json")
    d = json.loads(store.get())
    pref_info = d[pref]
    pref_info2 = []
    tz_jst = timezone(timedelta(hours=9), name="JST")
    now = datetime.now(tz=tz_jst)
    for x in pref_info:
        d = x.copy()
        d["include_now"] = include_now(now, x["date_from"], x["date_to"])
        pref_info2.append(d)
    store2 = datastore.store(f"{pref_en}.json")
    s = store2.get()
    pref_info_prev = None if s is None else json.loads(s)
    if pref_info2 != pref_info_prev:
        post, url_start, url_end, url = show(pref_info2, pref, pref_en)
        if dry_run:
            print(post)
        else:
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            if url_start is None:
                bsky_post = post
            else:
                bsky_post = {
                    "$type": "app.bsky.feed.post",
                    "text": post,
                    "createdAt": now,
                    "facets": [
                        {
                            "index": {"byteStart": url_start, "byteEnd": url_end},
                            "features": [
                                {
                                    "$type": "app.bsky.richtext.facet#link",
                                    "uri": url,
                                }
                            ],
                        }
                    ],
                }
            bsky = Client(bsky_user, bsky_password)
            r = bsky.post(bsky_post)
            if "error" in r:
                print(bsky_post)
                print(r)
                raise Exception(r["message"])
            mstdn = Mastodon(
                access_token=mstdn_access_token, api_base_url=mstdn_api_base_url
            )
            mstdn.toot(post)
        if not no_save:
            store2.put(json.dumps(pref_info2))


if __name__ == "__main__":
    handler(None, None)
