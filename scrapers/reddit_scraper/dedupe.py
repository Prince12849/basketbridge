"""In-memory deduplication tracking for posts and comments across queries
and subreddits (the same post can legitimately show up in multiple search
results)."""

from __future__ import annotations


class SeenTracker:
    def __init__(self) -> None:
        self._seen_posts: set[str] = set()
        self._seen_comments: set[str] = set()

    def is_new_post(self, post_id: str) -> bool:
        if post_id in self._seen_posts:
            return False
        self._seen_posts.add(post_id)
        return True

    def is_new_comment(self, comment_id: str) -> bool:
        if comment_id in self._seen_comments:
            return False
        self._seen_comments.add(comment_id)
        return True

    def has_post(self, post_id: str) -> bool:
        return post_id in self._seen_posts

    @property
    def post_count(self) -> int:
        return len(self._seen_posts)

    @property
    def comment_count(self) -> int:
        return len(self._seen_comments)
