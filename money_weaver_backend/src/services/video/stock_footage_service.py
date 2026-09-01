import requests
import os
import random
from typing import List, Dict, Tuple, Optional
import time
import cv2
import sys
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from services.script_parsing_service import script_parsing_service

class StockFootageService:
    def __init__(self):
        self.pexels_api_key = os.getenv('PEXELS_API_KEY')
        self.pixabay_api_key = os.getenv('PIXABAY_API_KEY')
        # Use consolidated directory at the project root level
        self.working_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'work')
        os.makedirs(self.working_dir, exist_ok=True)
        # For testing, we'll use sample videos if no API keys are configured
        self.use_sample_videos = not (self.pexels_api_key or self.pixabay_api_key)
    
    # Words that describe mood/lighting/motion rather than a searchable visual
    # subject. Keyword extraction should avoid these so queries return real
    # footage instead of "dimly lit" -> random close-ups.
    _WEAK_VISUAL_WORDS = {
        "dimly", "lit", "filled", "bustling", "quiet", "dark", "bright", "large",
        "small", "little", "emotional", "hopeful", "nervous", "tense", "slow",
        "fast", "cinematic", "dramatic", "beautiful", "general", "some", "various",
        "many", "two", "three", "the", "this", "that", "these", "those",
    }

    def _extract_keywords(self, text: str, max_keywords: int = 3) -> List[str]:
        """Extract concrete, searchable visual keywords from a shot description.

        Prefers noun phrases (e.g. \"comedy club\") and substantive nouns over
        generic mood/lighting words, so stock searches return relevant footage.
        """
        if not text:
            return []

        # Clean the text: lowercase, strip punctuation, collapse whitespace
        cleaned_text = re.sub(r'[^\w\s]', ' ', text.lower())
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        words = cleaned_text.split()

        # Keep meaningful content words (not stop words / weak visual fillers)
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'among', 'is', 'are', 'was',
            'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'an', 'as', 'so', 'if', 'it', 'a',
        }
        meaningful = [
            w for w in words
            if w not in stop_words and len(w) > 2 and w not in self._WEAK_VISUAL_WORDS
        ]

        # Build phrase candidates first (adjacent meaningful pairs), then singles.
        phrases = [f"{a} {b}" for a, b in zip(meaningful, meaningful[1:])]
        candidates = list(dict.fromkeys(phrases + meaningful))
        return candidates[:max_keywords]
    
    def _generate_search_queries(self, shot_description: str, voiceover_text: str, max_queries: int = 3) -> List[str]:
        """
        Generate search queries based on shot description and voiceover text
        """
        queries = []
        shot_keywords = self._extract_keywords(shot_description, 3)
        voiceover_keywords = self._extract_keywords(voiceover_text, 2)

        if shot_keywords:
            queries.append(shot_keywords[0])
        if voiceover_keywords and voiceover_keywords[0] not in queries:
            queries.append(voiceover_keywords[0])
        if len(shot_keywords) > 1:
            queries.append(shot_keywords[1])

        # Remove duplicates and limit
        unique_queries = list(dict.fromkeys(queries))[:max_queries]
        return unique_queries if unique_queries else ["nature"]  # Fallback to "nature"

    def _llm_scene_queries(self, scenes: List[Dict]) -> Dict[int, List[str]]:
        """Generate on-theme stock-video search phrases per scene with the LLM.

        Returns {scene_index: [query, ...]} so each scene searches with a
        concrete, visual query (real places/objects/people/actions) instead of
        naive keyword extraction. Returns {} on any failure so callers fall back.
        """
        try:
            from services.llm_service import llm_service
        except Exception as e:
            print(f"LLM query generation unavailable: {e}")
            return {}

        descriptors = []
        for i, s in enumerate(scenes):
            visual = (s.get('visual_description') or s.get('description') or '').strip()
            voice = (s.get('voiceover') or '').strip()
            descriptors.append(f"Scene {i}: VISUAL: {visual} | VOICEOVER: {voice}")

        if not descriptors:
            return {}

        prompt = (
            "You generate stock-video footage search phrases. For each scene, give 1-2 short "
            "search queries (each <=6 words) that describe CONCRETE, SEARCHABLE visual content the "
            "camera shows: real places, objects, people, actions. Do NOT describe emotions, metaphors, "
            "story meaning, or paraphrase the voiceover. Do NOT use placeholders. Return ONLY JSON:\n"
            '{"queries":[{"scene":0,"query":["comedy club stage","audience laughing"]},'
            '{"scene":1,"query":["stand up comedian microphone"]}]}\n\n'
            "SCENES:\n" + "\n".join(descriptors)
        )

        try:
            model = os.getenv("SCRIPT_MODEL") or "openai/gpt-4o-mini"
            gen_kwargs = dict(max_tokens=1600, temperature=0.2)
            # Gemini first (rotating keys = several 20/day buckets), then the
            # OpenRouter pool. The paid openai/gpt-4o-mini default is kept only
            # as a last resort because it 402s ("can only afford 53 tokens")
            # whenever the primary OpenRouter balance is spent.
            raw = None
            if self._gemini_keys():
                raw = self._gemini_text(
                    prompt, os.getenv('GEMINI_MODEL') or 'gemini-2.5-flash-lite',
                    max_tokens=1600)
            if raw is None:
                raw = self._openrouter_text_fallback(
                    model, prompt, gen_kwargs)
            data = llm_service._extract_json(raw)
            if not isinstance(data, dict):
                return {}
            out = {}
            for entry in data.get('queries', []):
                scene = entry.get('scene')
                qs = [str(q).strip() for q in (entry.get('query') or []) if str(q).strip()]
                if isinstance(scene, int) and qs:
                    out[scene] = qs[:3]
            return out
        except Exception as e:
            print(f"LLM query generation failed: {e}")
            return {}

    @staticmethod
    def _preview_url(video_data) -> Optional[str]:
        """A publicly fetchable preview thumbnail for a search result item,
        used to vision-verify the clip is on-theme before downloading it."""
        img = video_data.get('image')
        if isinstance(img, str) and img.startswith('http'):
            return img
        return None

    @staticmethod
    def _gemini_keys():
        """Ordered list of Gemini API keys to try (primary + comma-separated
        fallbacks). Free tier caps each PROJECT at 20 req/day, so multiple keys
        = multiple 20/day buckets. The first 429 is a quota signal, not an
        error - rotate to the next key before falling back entirely."""
        primary = os.getenv('GEMINI_API_KEY') or ''
        fallbacks = [k.strip() for k in
                     (os.getenv('GEMINI_API_KEY_FALLBACKS') or '').split(',')
                     if k.strip()]
        keys = list(dict.fromkeys([primary] + fallbacks))
        return [k for k in keys if k]

    @staticmethod
    def _openrouter_keys():
        """Ordered OpenRouter keys: primary + OPENROUTER_API_KEY_FALLBACKS.
        Each key brings its own balance / free-model-day bucket."""
        primary = os.getenv('OPENROUTER_API_KEY') or ''
        fallbacks = [k.strip() for k in
                     (os.getenv('OPENROUTER_API_KEY_FALLBACKS') or '').split(',')
                     if k.strip()]
        keys = list(dict.fromkeys([primary] + fallbacks))
        return [k for k in keys if k]

    def _openrouter_text_fallback(self, model, prompt, gen_kwargs):
        """Try each OpenRouter key until one responds. Uses the LLM service for
        the actual call but rotates the api key through the pool (each key's
        balance/free-day bucket is separate)."""
        from services.llm_service import llm_service
        orig = os.environ.get('OPENROUTER_API_KEY')
        try:
            for k in self._openrouter_keys():
                os.environ['OPENROUTER_API_KEY'] = k
                try:
                    raw = llm_service._chat_free_resilient(
                        None, model, [{'role': 'user', 'content': prompt}], **gen_kwargs)
                    if raw:
                        return raw
                except Exception as e:
                    print(f"openrouter key {k[:10]}... failed: {str(e)[:80]}")
            return None
        finally:
            if orig is None:
                os.environ.pop('OPENROUTER_API_KEY', None)
            else:
                os.environ['OPENROUTER_API_KEY'] = orig

    def _gemini_vision_score(self, image_url, description, voiceover):
        """Vision score via Google Gemini (free-tier friendly). Returns 0-5 or
        None on failure. Used when GEMINI_API_KEY is set; otherwise falls back
        to OpenRouter."""
        try:
            import base64 as _b64
            import json as _json
            import re as _re
            keys = self._gemini_keys()
            if not keys:
                return None
            if image_url.startswith('data:image/'):
                b64str = image_url.split(',', 1)[1]
            else:
                r = requests.get(image_url, timeout=30)
                if r.status_code != 200:
                    return None
                b64str = _b64.b64encode(r.content).decode()
            payload = {
                'contents': [{
                    'parts': [
                        {'text': (
                            'Does this stock-video thumbnail show the subject the scene needs? '
                            f'Scene subject: {description[:140]}. '
                            'Reply ONLY JSON: {"on_theme": true/false, "relevance": 0-5}. '
                            'on_theme=false only when clearly unrelated (wrong subject, '
                            'animal/food symbols, empty landscape); stories set in a '
                            'comedy club qualify even when described abstractly.')},
                        {'inline_data': {
                            'mime_type': 'image/jpeg' if 'image/jpeg' in image_url else 'image/png',
                            'data': b64str,
                        }},
                    ],
                }],
                'generationConfig': {'maxOutputTokens': 400, 'temperature': 0.1},
            }
            model = os.getenv('VISION_MODEL_GEMINI') or 'gemini-2.5-flash'
            r = None
            for key in keys:
                r = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                    params={'key': key}, json=payload, timeout=40)
                if r.status_code == 200:
                    break
                print(f"gemini vision status: {r.status_code} {r.text[:150]}")
                # 429 = this key's 20/day quota exhausted; next key may still
                # have budget. Non-429 (400/500) is not a quota issue - bail.
                if r.status_code != 429:
                    return None
            if r is None or r.status_code != 200:
                return None
            cand = r.json()['candidates'][0]
            if cand.get('finishReason') == 'SAFETY':
                print("gemini vision SAFETY refusal")
                return None
            parts = cand['content']['parts']
            content = ''.join(p.get('text', '') for p in parts)
            m = _re.search(r'\{.*\}', content, _re.DOTALL)
            if not m:
                return None
            d = _json.loads(m.group(0))
            if not isinstance(d, dict):
                return None
            if d.get('on_theme') is False:
                return 0
            return max(0, int(d.get('relevance') or 3))
        except Exception as e:
            print(f"gemini vision score failed: {e}")
            return None

    def _gemini_text(self, prompt, model='gemini-2.5-flash', max_tokens=1200):
        """Gemini text completion via free-tier API; returns string or None.

        Free tier is throttled (~20 req/min, RESOURCE_EXHAUSTED on burst), so
        on a 429 we wait for the retry window and retry once (bounded), giving
        a single scene's batch a fair chance without stalling the whole render.
        """
        try:
            import json as _json
            keys = self._gemini_keys()
            if not keys:
                return None
            url = (f'https://generativelanguage.googleapis.com/v1beta/models/'
                   f'{model}:generateContent')
            payload = {'contents': [{'parts': [{'text': prompt}]}],
                       'generationConfig': {'maxOutputTokens': max_tokens, 'temperature': 0.1}}
            r = None
            for key in keys:
                r = requests.post(url, params={'key': key}, json=payload, timeout=45)
                if r.status_code == 200:
                    break
                print(f"gemini text status: {r.status_code} {r.text[:150]}")
                if r.status_code != 429:
                    return None
            if r is None or r.status_code != 200:
                return None
            parts = r.json()['candidates'][0]['content']['parts']
            return ''.join(p.get('text', '') for p in parts)
        except Exception as e:
            print(f"gemini text failed: {e}")
            return None

    def _vision_score(self, image_url, description, voiceover):
        """0-5 relevance that a clip matches the scene; None on any failure.

        Tries Gemini first (free-tier friendly when GEMINI_API_KEY is set),
        then OpenRouter. Returns None when both are unavailable."""
        if not image_url:
            return None
        if not os.getenv('VISION_MODEL'):
            # No explicit OpenRouter vision model: try Gemini free tier first.
            score = self._gemini_vision_score(image_url, description, voiceover)
            if score is not None:
                return score
        try:
            import json as _json
            import re as _re
            payload = {
                'model': os.getenv('VISION_MODEL') or 'openai/gpt-4o-mini',
                'messages': [{'role': 'user', 'content': [
                    {'type': 'image_url', 'image_url': {'url': image_url}},
                    {'type': 'text', 'text': (
                        'You judge whether a stock-video thumbnail matches a scene. '
                        'Reject clips that show something clearly unrelated to the scene '
                        '(e.g. an animal or unrelated subject when the scene needs a person on a stage). '
                        f'Scene shows: {description}. Voiceover: {voiceover}. '
                        'Reply ONLY JSON: {"on_theme": true/false, "relevance": 0-5}. '
                        'Set on_theme=false only when clearly unrelated.')},
                ]}],
                'max_tokens': 60,
            }
            content = None
            for k in self._openrouter_keys():
                r = requests.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    json=payload,
                    headers={'Authorization': 'Bearer ' + k},
                    timeout=60)
                if r.status_code == 200:
                    content = r.json()['choices'][0]['message']['content']
                    break
                if r.status_code != 429:
                    # 402 = this key out of balance: try the next key.
                    print(f"openrouter vision {r.status_code}: {r.text[:100]}")
                    if r.status_code != 402:
                        break
            if content is None:
                return None
            m = _re.search(r'\{.*\}', content, _re.DOTALL)
            if not m:
                return None
            d = _json.loads(m.group(0))
            if not isinstance(d, dict):
                return None
            if d.get('on_theme') is False:
                return 0
            return max(0, int(d.get('relevance') or 3))
        except Exception as e:
            print(f"vision score failed: {e}")
            return None

    def _text_scores(self, labels, description, voiceover, story_context=None):
        """For each candidate label return a 0-5 on-theme relevance (None if
        undecidable). Text-based counterpart of _vision_score: uses the
        providers' own alt/tags text, so it works without image tokens (e.g.
        when the vision model's budget is exhausted). Batches all candidates of
        a scene into one LLM call.

        story_context (str, e.g. 'a comedy-club-heckler story set on a stage') is
        the GLOBAL setting of the whole video, so a clip of the story's setting
        is scored on-theme even for scenes whose own description is abstract."""
        try:
            from services.llm_service import llm_service
            import json as _json
            import re as _re
            numbered = "\n".join(f"{i}. {lb}" for i, lb in enumerate(labels))
            ctx = f" CONTEXT: the whole video is {story_context}." if story_context else ""
            prompt = (
                'You judge which stock-video clip descriptions can visually serve a scene. '
                f"{ctx} Scene shows: {description}. Voiceover: {voiceover}.\n"
                f"CLIPS:\n{numbered}\n"
                'Reply ONLY JSON: {"scores": [{"i": 0, "on_theme": true/false, "relevance": 0-5}, ...]}. '
                'on_theme=false only for clearly unrelated content (wrong/or absent subject, '
                'food/animal symbols, empty landscape). Clips of the story setting qualify. '
                'Relevance 3+ = usable b-roll; 0-1 = useless for this scene.')
            model = os.getenv("RERANK_TEXT_MODEL") or os.getenv("SCRIPT_MODEL") or "openai/gpt-4o-mini"
            gen_kwargs = dict(max_tokens=800, temperature=0.1)
            # Gemini first: rotate across GEMINI_API_KEY + fallback keys (each
            # has its own 20/day free quota), then the OpenRouter key pool.
            raw = None
            if self._gemini_keys():
                raw = self._gemini_text(
                    prompt, os.getenv('GEMINI_MODEL') or 'gemini-2.5-flash-lite',
                    max_tokens=1200)
            if raw is None:
                raw = self._openrouter_text_fallback(model, prompt, gen_kwargs)
            m = _re.search(r'\{.*\}', raw or '', _re.DOTALL)
            if not m:
                return [None] * len(labels)
            # Parse per-record so a token-truncated (cut-off) JSON tail still
            # yields the scores for the records that did arrive.
            out = [None] * len(labels)
            for rm in _re.finditer(
                    r'"i"\s*:\s*(\d+).{0,200}?"on_theme"\s*:\s*(true|false)'
                    r'.{0,50}?"relevance"\s*:\s*(\d+)',
                    m.group(0).replace('\n', ' ')[:12000], _re.DOTALL):
                try:
                    i = int(rm.group(1))
                except (TypeError, ValueError):
                    continue
                if not (0 <= i < len(labels)):
                    continue
                if rm.group(2) == 'false':
                    out[i] = 0
                else:
                    try:
                        out[i] = max(0, min(5, int(rm.group(3))))
                    except (TypeError, ValueError):
                        out[i] = None
            return out
        except Exception as e:
            print(f"text scores failed: {e}")
            return [None] * len(labels)

    @staticmethod
    def _candidate_text_label(video_data) -> Optional[str]:
        """Human-readable self-description of a search result (its own alt
        text / tags / description), used for text-based relevance scoring."""
        parts = []
        for k in ('alt', 'description', 'tags', 'name'):
            v = video_data.get(k)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
        return '; '.join(parts) or None

    @staticmethod
    def _script_story_context(scenes):
        """One-sentence global setting of the video (first scene's visual +
        genre words), used to keep the story's setting clips on-theme."""
        try:
            first = (scenes[0].get('visual_description') or scenes[0].get('description') or '')
            return first[:120]
        except (IndexError, AttributeError, TypeError):
            return None

    def _rerank_candidates(self, all_videos, description, voiceover, scenes=None):
        """Drop off-theme candidates and order the rest by relevance.

        Uses the batched TEXT score for all candidates first (one LLM call per
        scene, fits free-tier rate limits), and only vision-checks candidates
        that arrive with a thumbnail when the text score is missing. Candidates
        with neither are kept (not dropped) but sorted after validated ones;
        the scene is never emptied. Scores are cached on the video dict."""
        # Deterministic blocklist: drop clearly-off-theme content even when the
        # LLM scorer is down (free-tier quota exhausted) or the label is thin.
        # These are the recurring offenders from a comedy-stage story: nature,
        # food/animal symbols, vehicles, sports, silhouette-only landscapes.
        OFF_THEME_KEYWORDS = (
            'butterfl', 'flower', 'meadow', 'railway', 'railroad', 'track',
            'golf', 'truck', 'ski', 'cat ', 'dog ', 'bird', 'puppy', 'kitten',
            'earbud', 'headphone', 'cake', 'food', 'pizza', 'sunset',
            'mountain', 'forest', 'beach', 'wave', 'leaf', 'garden',
            'silhouette', 'sunrise', 'dandelion', 'bird feeding',
            'duck', 'rabbit', 'bunny', 'squirrel', 'goat', 'sheep', 'cow ',
            'horse', 'deer', 'fox', 'owl', 'eagle', 'pigeon', 'parrot',
            'swan', 'goose', 'hen', 'rooster', 'turtle', 'frog', 'snake',
            'fish ', 'whale', 'dolphin', 'seal', 'penguin', 'bear ',
            'rat ', 'mouse', 'lizard', 'insect', 'bee ', 'ant ', 'spider',
            'monkey', 'elephant', 'lion', 'tiger', 'workout', 'pushup',
            'push-up', 'basketball', 'football', 'soccer', 'tennis',
            'athlete', 'fitness', 'gym ', 'weights', 'sport',
        )
        scored = []
        pending = []   # candidates that still need a vision-based score
        labels = []
        for v in all_videos:
            cached = v.get('_relevance_score')
            if cached is not None:
                if cached < 2:
                    continue
                scored.append((v, cached))
                continue
            label = self._candidate_text_label(v)
            if label and any(kw in label.lower() for kw in OFF_THEME_KEYWORDS):
                continue  # deterministic off-theme (e.g. butterfly/earbuds)
            if not label:
                img = self._preview_url(v)
                if img:
                    pending.append((v, None, None))
                else:
                    scored.append((v, None))  # no info at all: keep, unvalidated
                continue
            labels.append((v, label))

        # Batched text score: one LLM call for the whole scene (cheap, no image
        # tokens, fits the free-tier rate limit).
        if labels:
            story = self._script_story_context(scenes or [])
            text_scores = self._text_scores(
                [lbl for _, lbl in labels], description, voiceover, story) or []
            for (v, _lbl), s in zip(labels, text_scores):
                if s is not None:
                    v['_relevance_score'] = s
                    if s < 2:
                        continue  # clearly off-theme, drop it
                    scored.append((v, s))
                else:
                    img = self._preview_url(v)
                    if img:
                        pending.append((v, None, None))
                    else:
                        scored.append((v, None))

        # Vision-scored fallback for candidates the text scorer could not
        # decide (but that have a thumbnail). Cached.
        for v, _lbl, _old in pending:
            score = self._vision_score(self._preview_url(v), description, voiceover)
            if score is not None:
                v['_relevance_score'] = score
                if score < 2:
                    continue  # clearly off-theme, drop it
            scored.append((v, score))

        if not scored:
            return all_videos  # never drop everything: keep original order

        def key(item):
            s = item[1]
            if s is None:
                return (2, 0)  # unvalidated: keep, but after validated on-theme
            return (0, -s)     # validated: higher relevance first

        scored.sort(key=key)
        return [v for v, _ in scored]

    def _validate_downloaded_video(self, video_path, description, voiceover):
        """Vision-check a downloaded clip's first frame; False only when it is
        clearly off-theme. Accepts on any failure so we never silently reject
        good footage (a scene is never emptied)."""
        try:
            import base64 as _b64
            import subprocess as _sp
            frame_path = os.path.join(
                self.working_dir, f'vf_{int(time.time() * 1000)}.jpg')
            r = _sp.run(
                ['ffmpeg', '-y', '-ss', '0', '-i', video_path, '-frames:v', '1',
                 '-vf', 'scale=320:-1', frame_path],
                capture_output=True, timeout=30)
            if r.returncode != 0 or not os.path.exists(frame_path):
                return True
            data = ('data:image/jpeg;base64,'
                    + _b64.b64encode(open(frame_path, 'rb').read()).decode())
            try:
                os.remove(frame_path)
            except Exception:
                pass
            score = self._vision_score(data, description, voiceover)
            return score is None or score >= 2
        except Exception as e:
            print(f"frame validate failed (accepting): {e}")
            return True

    def search_pexels_videos(self, query: str, per_page: int = 5, orientation: str = "landscape", min_width: int = 1280, min_height: int = 720) -> List[Dict]:
        """Search for videos on Pexels with resolution and orientation parameters"""
        if not self.pexels_api_key:
            print("Warning: Pexels API key not configured")
            return []
        
        try:
            # Map orientation values for Pexels API
            pexels_orientation = "landscape"  # Default
            if orientation == "portrait":
                pexels_orientation = "portrait"
            elif orientation == "square":
                pexels_orientation = "square"
            # landscape remains as "landscape"
            
            url = "https://api.pexels.com/videos/search"
            headers = {"Authorization": self.pexels_api_key}
            params = {
                "query": query,
                "per_page": per_page,
                "orientation": pexels_orientation,
                "min_width": min_width,
                "min_height": min_height
            }
            
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('videos', [])[:per_page]
        except Exception as e:
            print(f"Error searching Pexels videos: {e}")
        
        return []
    
    def search_pixabay_videos(self, query: str, per_page: int = 5, orientation: str = "horizontal", min_width: int = 1280, min_height: int = 720) -> List[Dict]:
        """Search for videos on Pixabay with resolution and orientation parameters"""
        if not self.pixabay_api_key:
            print("Warning: Pixabay API key not configured")
            return []
        
        try:
            # Map orientation values for Pixabay API
            pixabay_orientation = "horizontal"  # Default
            if orientation == "portrait":
                pixabay_orientation = "vertical"
            elif orientation == "square":
                # For square, we can use either horizontal or vertical and crop later
                pixabay_orientation = "horizontal"
            # landscape maps to "horizontal"
            
            url = "https://pixabay.com/api/videos/"
            params = {
                "key": self.pixabay_api_key,
                "q": query,
                "per_page": per_page,
                "video_type": "film",
                "orientation": pixabay_orientation,
                "min_width": min_width,
                "min_height": min_height
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('hits', [])[:per_page]
        except Exception as e:
            print(f"Error searching Pixabay videos: {e}")
        
        return []
    
    def get_video_duration(self, video_path: str) -> float:
        """Get the duration of a video file in seconds"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps
            cap.release()
            return duration
        except Exception as e:
            print(f"Error getting video duration: {e}")
            return 0.0
    
    def download_video(self, video_url: str, filename: str) -> str:
        """Download a video file"""
        try:
            filepath = os.path.join(self.working_dir, filename)
            
            # Check if file already exists
            if os.path.exists(filepath):
                return filepath
            
            response = requests.get(video_url, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return filepath
        except Exception as e:
            print(f"Error downloading video: {e}")
        
        return None
    
    def get_stock_videos_for_script(self, script: str, target_scenes: List[Dict] = None, max_videos: int = 10, 
                                   orientation: str = "landscape", min_width: int = 1280, min_height: int = 720) -> List[Tuple[str, float, Dict]]:
        """
        Get stock videos based on script content with duration information and resolution settings
        
        Returns:
            List[Tuple[video_path, duration, scene_info]]
        """
        print(f"Getting stock videos for script (max_videos={max_videos}, orientation={orientation}, min_width={min_width}, min_height={min_height})")
        # If we're in testing mode (no API keys), use sample videos
        if self.use_sample_videos:
            print("Using sample videos for testing")
            return self._get_sample_videos_with_duration(max_videos)
        
        # Parse script to get shot descriptions if target_scenes not provided
        if target_scenes is None:
            parsed_script = script_parsing_service.parse_script(script)
            scenes = parsed_script.get('scenes', [])
        else:
            scenes = target_scenes
        
        print(f"Processing {len(scenes)} scenes")

        # Generate on-theme, per-scene search queries once up front (LLM),
        # falling back to naive keyword extraction per scene if it fails.
        queries_by_scene = self._llm_scene_queries(scenes)

        video_files = []
        downloaded_count = 0
        used_video_urls = set()  # Track URLs to prevent duplicates
        
        for i, scene in enumerate(scenes):
            if downloaded_count >= max_videos:
                break
                
            shot_desc = scene.get('visual_description', '')
            voiceover_text = scene.get('voiceover', '')
            
            print(f"Processing scene {i+1}: {shot_desc}")
            print(f"Voiceover text: {voiceover_text}")
            
            # Generate better search queries
            search_queries = queries_by_scene.get(i) or self._generate_search_queries(shot_desc, voiceover_text, 3)
            print(f"Generated search queries: {search_queries}")
            
            # Try each query until we find videos
            all_videos = []
            for query in search_queries:
                if len(all_videos) >= 6:  # Limit total videos per scene
                    break
                    
                print(f"Searching for videos with query: {query}")
                # Search on both platforms with resolution and orientation parameters
                pexels_videos = self.search_pexels_videos(query, 3, orientation, min_width, min_height)
                pixabay_videos = self.search_pixabay_videos(query, 3, orientation, min_width, min_height)
                print(f"Found {len(pexels_videos)} Pexels videos and {len(pixabay_videos)} Pixabay videos")
                
                # Combine results
                scene_videos = pexels_videos + pixabay_videos
                
                # Add scene context to each video
                for video_data in scene_videos:
                    video_data['_scene_context'] = {
                        'query': query,
                        'scene_index': i,
                        'scene_description': shot_desc
                    }
                
                all_videos.extend(scene_videos)
            
            # Rerank candidates: drop off-theme clips (e.g. an animal when
            # the scene needs a person on a stage) and order the rest by relevance.
            # Vision is used when a thumbnail is available; otherwise the
            # candidate's own text description is judged. Falls back to the
            # gathered order (shuffled) when the LLM is unavailable so a scene
            # is never left empty.
            try:
                all_videos = self._rerank_candidates(all_videos, shot_desc, voiceover_text, scenes)
                print(f"Reranked scene {i+1} to {len(all_videos)} on-theme candidates")
            except Exception as e:
                print(f"Rerank failed for scene {i+1}, keeping original order: {e}")
                random.shuffle(all_videos)
            
            # Process videos, avoiding duplicates (a scene uses 2-3 clips; cap
            # successful downloads per scene so late scenes are not starved by
            # earlier ones hoarding the global max_videos budget).
            scene_downloads = 0
            for video_data in all_videos:
                if downloaded_count >= max_videos:
                    break
                if scene_downloads >= 3:
                    break  # this scene has enough; keep budget for later scenes
                
                # Get video URL and metadata
                video_url = None
                video_metadata = {}
                
                if 'video_files' in video_data:  # Pexels format
                    # Choose the file closest to the target height, but never
                    # 4K+ — avoids huge downloads that can fill the disk.
                    target_h = min_height or 720
                    best_file = None
                    for file_info in video_data['video_files']:
                        h = file_info.get('height', 0)
                        if h > 2160:
                            continue
                        if best_file is None:
                            best_file = file_info
                            continue
                        bh = best_file.get('height', 0)
                        chosen = abs(h - target_h) < abs(bh - target_h) or (
                            abs(h - target_h) == abs(bh - target_h) and h < bh)
                        if chosen:
                            best_file = file_info
                    
                    # If no reasonable-sized file found, use the first available
                    if not best_file and video_data['video_files']:
                        best_file = video_data['video_files'][0]
                    
                    if best_file:
                        video_url = best_file['link']
                        video_metadata = {
                            'width': best_file.get('width', 0),
                            'height': best_file.get('height', 0),
                            'fps': best_file.get('fps', 30),
                            'file_type': best_file.get('file_type', 'video/mp4'),
                            'quality': best_file.get('quality', 'unknown')
                        }
                    
                    # Add Pexels-specific metadata
                    video_metadata.update({
                        'pexels_id': video_data.get('id'),
                        'pexels_duration': video_data.get('duration', 0),
                        'pexels_width': video_data.get('width', 0),
                        'pexels_height': video_data.get('height', 0),
                        'description': shot_desc,
                        'source': 'pexels',
                        'search_query': video_data.get('_scene_context', {}).get('query', ''),
                        'scene_index': video_data.get('_scene_context', {}).get('scene_index', -1)
                    })
                elif 'videos' in video_data:  # Pixabay format
                    # Pixabay returns a dict with quality keys like 'large', 'medium', etc.
                    if video_data['videos']:
                        # Prefer large quality, fallback to medium, then small
                        videos_dict = video_data['videos']
                        selected_quality = None
                        video_info = None
                        
                        if 'large' in videos_dict:
                            selected_quality = 'large'
                            video_info = videos_dict['large']
                        elif 'medium' in videos_dict:
                            selected_quality = 'medium'
                            video_info = videos_dict['medium']
                        elif 'small' in videos_dict:
                            selected_quality = 'small'
                            video_info = videos_dict['small']
                        else:
                            # Get first available quality
                            first_quality = next(iter(videos_dict), None)
                            if first_quality and isinstance(videos_dict[first_quality], dict):
                                selected_quality = first_quality
                                video_info = videos_dict[first_quality]
                        
                        if video_info:
                            video_url = video_info.get('url')
                            video_metadata = {
                                'width': video_info.get('width', 0),
                                'height': video_info.get('height', 0),
                                'quality': selected_quality,
                                'file_type': 'video/mp4',
                                'description': shot_desc,
                                'source': 'pixabay',
                                'pixabay_id': video_data.get('id'),
                                'pixabay_duration': video_data.get('duration', 0),
                                'pixabay_tags': video_data.get('tags', ''),
                                'search_query': video_data.get('_scene_context', {}).get('query', ''),
                                'scene_index': video_data.get('_scene_context', {}).get('scene_index', -1)
                            }
                
                # Check if we have a valid URL and it hasn't been used recently
                if video_url and video_url not in used_video_urls:
                    print(f"Downloading video from: {video_url}")
                    filename = f"stock_{int(time.time())}_{downloaded_count}.mp4"
                    filepath = self.download_video(video_url, filename)
                    if filepath:
                        print(f"Downloaded video to: {filepath}")
                        # Verify the actual pixels are on-theme (catches off-theme
                        # clips even when the provider gives no thumbnail).
                        if not self._validate_downloaded_video(filepath, shot_desc, voiceover_text):
                            print(f"Rejected off-theme clip, trying next candidate")
                            try:
                                os.remove(filepath)
                            except Exception:
                                pass
                            used_video_urls.add(video_url)  # don't re-try this clip
                            continue
                        # Get video duration using metadata if available, otherwise calculate
                        duration = video_metadata.get('pexels_duration') or video_metadata.get('pixabay_duration') or self.get_video_duration(filepath)
                        print(f"Video duration: {duration} seconds")
                        
                        # Add the actual file duration to metadata
                        video_metadata['actual_duration'] = duration
                        video_metadata['file_path'] = filepath
                        
                        video_files.append((filepath, duration, video_metadata))
                        used_video_urls.add(video_url)  # Track this URL
                        downloaded_count += 1
                        scene_downloads += 1
                    else:
                        print("Failed to download video")
                elif video_url in used_video_urls:
                    print(f"Skipping duplicate video: {video_url}")
                else:
                    print("No video URL found")
        
        print(f"Returning {len(video_files)} video files with duration info")
        return video_files
    
    def _get_sample_videos_with_duration(self, max_videos: int = 10) -> List[Tuple[str, float, Dict]]:
        """Get sample videos for testing when no API keys are configured"""
        print("Using sample videos for testing (no API keys configured)")
        
        # Look for sample videos in the work directory
        sample_videos = []
        for filename in os.listdir(self.working_dir):
            if filename.startswith('sample') and filename.endswith('.mp4'):
                filepath = os.path.join(self.working_dir, filename)
                duration = self.get_video_duration(filepath)
                sample_videos.append((filepath, duration, {
                    'description': 'sample video', 
                    'source': 'local',
                    'actual_duration': duration,
                    'file_path': filepath,
                    'width': 1280,
                    'height': 720,
                    'fps': 30
                }))
        
        # If we don't have enough sample videos, create more
        while len(sample_videos) < max_videos:
            index = len(sample_videos) + 1
            sample_file = os.path.join(self.working_dir, f'sample{index}.mp4')
            
            # If the file doesn't exist, create it
            if not os.path.exists(sample_file):
                self._create_sample_video(sample_file)
            
            duration = self.get_video_duration(sample_file)
            sample_videos.append((sample_file, duration, {
                'description': 'sample video', 
                'source': 'local',
                'actual_duration': duration,
                'file_path': sample_file,
                'width': 1280,
                'height': 720,
                'fps': 30
            }))
        
        return sample_videos[:max_videos]
    
    def _create_sample_video(self, filepath: str):
        """Create a sample video file for testing"""
        try:
            # Create a simple test video using ffmpeg
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-f', 'lavfi',
                '-i', 'testsrc2=duration=5:size=1280x720:rate=30',
                '-vf', f'hue=s={random.random()}',  # Add some variation
                filepath
            ]
            
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error creating sample video: {result.stderr}")
        except Exception as e:
            print(f"Error creating sample video: {e}")

# Global instance
stock_service = StockFootageService()