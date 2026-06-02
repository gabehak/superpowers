#!/usr/bin/env python3
"""
Pull YouTube comments from your channel's recent videos.

Setup:
  pip install google-api-python-client openpyxl pandas

Usage:
  export YOUTUBE_API_KEY=your_key
  export YOUTUBE_CHANNEL_ID=UCxxxxxxxxxxxxxxxx
  python scripts/pull_comments.py --videos 5 --comments 200
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("pip install google-api-python-client", file=sys.stderr)
    sys.exit(1)

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID", "")
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def get_youtube():
    if not API_KEY:
        print("ERROR: set YOUTUBE_API_KEY", file=sys.stderr)
        sys.exit(1)
    return build("youtube", "v3", developerKey=API_KEY)


def get_recent_videos(yt, channel_id: str, max_videos: int = 5) -> list[dict]:
    """Get the most recent uploads from a channel."""
    # Get uploads playlist ID
    resp = yt.channels().list(
        part="contentDetails,snippet",
        id=channel_id,
    ).execute()

    if not resp.get("items"):
        print(f"ERROR: channel {channel_id} not found", file=sys.stderr)
        sys.exit(1)

    channel_title = resp["items"][0]["snippet"]["title"]
    uploads_id = resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"Channel: {channel_title}")

    videos = []
    page_token = None
    while len(videos) < max_videos:
        params = {
            "part": "snippet",
            "playlistId": uploads_id,
            "maxResults": min(50, max_videos - len(videos)),
        }
        if page_token:
            params["pageToken"] = page_token

        resp = yt.playlistItems().list(**params).execute()
        for item in resp.get("items", []):
            snip = item["snippet"]
            videos.append({
                "video_id": snip["resourceId"]["videoId"],
                "title": snip["title"],
                "published_at": snip["publishedAt"],
            })

        page_token = resp.get("nextPageToken")
        if not page_token or len(videos) >= max_videos:
            break

    return videos[:max_videos]


def get_comments(yt, video_id: str, video_title: str, max_comments: int = 100) -> list[dict]:
    """Pull top-level comments for a single video."""
    comments = []
    page_token = None

    while len(comments) < max_comments:
        try:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, max_comments - len(comments)),
                "order": "relevance",
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token

            resp = yt.commentThreads().list(**params).execute()

            for item in resp.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "video_id": video_id,
                    "video_title": video_title,
                    "comment_id": item["id"],
                    "author": top.get("authorDisplayName", ""),
                    "text": top.get("textDisplay", ""),
                    "likes": top.get("likeCount", 0),
                    "reply_count": item["snippet"].get("totalReplyCount", 0),
                    "published_at": top.get("publishedAt", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}&lc={item['id']}",
                })

            page_token = resp.get("nextPageToken")
            if not page_token:
                break
            time.sleep(0.1)

        except HttpError as e:
            if "commentsDisabled" in str(e):
                print(f"  (comments disabled on {video_id})")
            else:
                print(f"  ERROR: {e}")
            break

    return comments[:max_comments]


def classify_comment(text: str) -> str:
    """Simple rule-based classification — replaced by AI analysis in analyze.py."""
    text_lower = text.lower()
    if "?" in text:
        return "question"
    if any(w in text_lower for w in ["thank", "great", "amazing", "love", "awesome", "helpful"]):
        return "positive_feedback"
    if any(w in text_lower for w in ["please make", "can you do", "video on", "tutorial on", "cover"]):
        return "content_request"
    if any(w in text_lower for w in ["wrong", "issue", "error", "broken", "fix", "bug"]):
        return "issue_report"
    return "general"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", type=int, default=5, help="Number of recent videos to pull from")
    parser.add_argument("--comments", type=int, default=200, help="Max comments per video")
    parser.add_argument("--channel", default=CHANNEL_ID, help="YouTube channel ID")
    parser.add_argument("--output", default=str(OUTPUT_DIR / "comments_raw.csv"))
    args = parser.parse_args()

    if not args.channel:
        print("ERROR: set YOUTUBE_CHANNEL_ID or pass --channel UCxxxxx", file=sys.stderr)
        sys.exit(1)

    yt = get_youtube()
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\nFetching {args.videos} most recent videos...")
    videos = get_recent_videos(yt, args.channel, args.videos)

    all_comments = []
    for v in videos:
        print(f"\n  [{v['video_id']}] {v['title'][:60]}")
        comments = get_comments(yt, v["video_id"], v["title"], args.comments)
        for c in comments:
            c["category"] = classify_comment(c["text"])
        all_comments.extend(comments)
        print(f"    → {len(comments)} comments")

    # Deduplicate by comment_id
    seen = set()
    deduped = []
    for c in all_comments:
        if c["comment_id"] not in seen:
            seen.add(c["comment_id"])
            deduped.append(c)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        fields = ["video_id", "video_title", "comment_id", "author", "text",
                  "likes", "reply_count", "published_at", "url", "category"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(deduped)

    print(f"\n✓ {len(deduped)} comments saved to {args.output}")
    print("Next: python scripts/analyze.py")


if __name__ == "__main__":
    main()
