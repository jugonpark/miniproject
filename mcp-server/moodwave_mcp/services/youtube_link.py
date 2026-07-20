from urllib.parse import urlencode


def create_youtube_music_url(track_title: str, artist_name: str) -> str:
    return f"https://music.youtube.com/search?{urlencode({'q': f'{track_title} {artist_name}'})}"
