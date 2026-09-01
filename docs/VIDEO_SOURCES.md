# VIDEO SOURCES

Master list. Free video pools for ingest.
Each entry: what it has, how to pull it.
Rule for ALL: read license per clip. Store it. No license -> no ingest.

---

## WAVE NOW — KEYLESS APIs (bulk ingest)

### Archive.org
- Has: old films, newsreels, ads, home movies. Prelinger. A/V Geeks. Stock Footage collection. Moving Image Archive. Public Domain Archive mirror.
- Pull: `advancedsearch.php?q=...&output=json` -> metadata API -> download MP4. Python lib `internetarchive`. Filter `licenseurl` / `rights` to PD or CC. Ingest offline, transcode.

### NASA Image & Video Library
- Has: space, rockets, Earth from orbit, science.
- Pull: `images-api.nasa.gov` JSON search. No key. Public domain.

### Library of Congress
- Has: early cinema, Americana, newsreels. National Screening Room. National Film Registry PD films.
- Pull: loc.gov JSON API. No key. Filter "Free to Use and Reuse" sets. MP4/ProRes downloads.

### Wikimedia Commons
- Has: places, animals, objects, encyclopedic b-roll. Mirrors Open Images, ESO, NASA uploads.
- Pull: MediaWiki API. Read license field per file. Mine `Commons:Free_media_resources/Video` page for more sources.

### Open Images (Sound & Vision, NL)
- Has: Dutch/European newsreels, archival film. Rich metadata (subjects, dates).
- Pull: OAI-PMH + Open Images API. CC/PD per record. Built for bulk reuse. Good first adapter after archive_org.

---

## WAVE NOW — KEYLESS SITES (scrape or hand-pick)

### Pexels
- Has: lifestyle, people, modern b-roll.
- Pull: API free. Already wired.

### Pixabay
- Has: wide variety, nature, abstract.
- Pull: API free. Already wired.

### Coverr
- Has: website hero loops, tech/product.
- Pull: API free. Show Coverr attribution.

### Mixkit
- Has: curated b-roll, travel, fashion, tech. Plus free music/SFX.
- Pull: no API. Scrape or hand-pick. Custom license: commercial OK, no credit, no account.

### Dareful
- Has: 4K nature, drone, landscapes. Small (~500 clips), high quality.
- Pull: site download, free account. CC BY 4.0 — credit required.

### Vidsplay
- Has: people, nature, textures. ~500 clips, weekly adds.
- Pull: direct MP4 download. Credit link required. Commercial OK.

### Life of Vids
- Has: lifestyle, urban, loops.
- Pull: site download. CC0. Limit: max 10 clips redistributed per platform. Hand-pick.

### Splitshire
- Has: cinematic single-author clips + photos.
- Pull: site download. Free commercial, no credit. Hand-pick.

### Mazwai
- Has: cinematic slow-mo, landscapes, experimental.
- Pull: site download. CC BY 3.0 (credit) or Mazwai license (no credit). People/property need releases for ads — check before commercial use.

### Videezy
- Has: drone, nature, motion graphics, overlays.
- Pull: free account. Free clips need credit. Some watermarked; higher res paid.

### Videvo
- Has: big mixed library, aerials, motion graphics. 500k+ clips total.
- Pull: site download. Per-clip license: Videvo Attribution License or CC BY 3.0. Check each clip.

### MotionElements free PD set
- Has: abstract, nature, motion graphics. 4000+ PD clips.
- Pull: public domain, no restrictions. ~5 downloads/week cap. One-time bulk ingest, then treat as static dataset.

### Free Nature Stock
- Has: nature only, one photographer.
- Pull: site download. Check per-clip terms.

### XStockvideo
- Has: HD b-roll. Nature, city, business, abstract.
- Pull: site download.

### PikWizard
- Has: big library, 1M+ assets.
- Pull: site download. Free license, no credit. No reselling raw clips.

### Motion Places
- Has: travel, cities, timelapse, by location.
- Pull: site download. CC BY — credit required.

### Beachfront B-Roll
- Has: HD b-roll, timelapse. Personal blog origin.
- Pull: hosted via Archive.org — pull through archive_org adapter, no separate scraper.

### CuteStockFootage
- Has: transitions, light leaks, FX overlays.
- Pull: site download. CC BY 4.0 — credit required.

### Free Stock Footage Archive
- Has: glitch, abstract, experimental.
- Pull: site download. CC BY 3.0 — credit required.

### Clipstill
- Has: cinemagraph loops.
- Pull: site, free monthly clips. Hand-pick.

---

## GOVERNMENT B-ROLL — PUBLIC DOMAIN

### CDC B-roll
- Has: health, labs, medical.
- Pull: site download. PD. Cite CDC. No endorsement implied.

### NPS B-roll (Grand Canyon + other parks)
- Has: landscapes, parks, monuments, timelapse.
- Pull: B-roll index pages, direct download. PD. No NPS endorsement implied.

### NASA YouTube
- Has: same NASA content, more volume.
- Pull: PD with credit. yt-dlp only for PD-verified items.

---

## SPACE / SCIENCE

### ESO videos
- Has: telescopes, space animation, observatories.
- Pull: site download. CC BY 4.0 — credit required. Many mirrored on Commons.

### ESA/Hubble videos
- Has: space animations, nebulae, satellites.
- Pull: site download, multiple sizes. Free with credit per ESA/Hubble rules.

---

## WAVE NEXT — FREE KEY

### Europeana
- Has: European heritage, art, history film.
- Pull: REST API. Free key via account signup. Filter rights CC0/PD.

### NARA
- Has: US government, military, 20th century history.
- Pull: Catalog API v2. Free read-only key by email request. Much content also mirrored on Archive.org.

### DPLA
- Has: aggregated US heritage. Some video.
- Pull: API, free key. Filter "Unlimited Re-Use". Check rights per record.

### Smithsonian Open Access
- Has: museum objects, science, history. Video subset.
- Pull: Open Access API (free data.gov key) or bulk CC0 download. CC0. Filter media type = video.

---

## WAVE LATER — CONSTRAINED

### YouTube CC
- Has: everything. Biggest long-tail pool.
- Pull: Data API with `license=creativeCommon`. 10k units/day ≈ 100 search calls. Trickle source, not a pool. yt-dlp only where CC verified on the video page.

### Vimeo CC
- Has: public domain channel, CC-filtered search.
- Pull: site scrape. Check license icon per video (CC0/CC BY). No bulk API path for this.

### Pond5 Public Domain Project
- Has: archival PD footage, animations, NASA mirrors.
- Pull: free account required to download. "Believed PD" — verify. This is NOT the paid Pond5 API.

### Freepik Video
- Has: motion graphics, SFX.
- Pull: free account. Attribution on free tier. Paid removes attribution.

### Vecteezy
- Has: vetted clips, model-released.
- Pull: free account. Attribution on free tier. 4K on many.

### PublicDomainFootage.com
- Has: newsreels, pop culture, civil rights, retro sports.
- Pull: PD content but downloads cost money. Skip until budget.

### Footage Farm
- Has: PD historical film archive.
- Pull: paid access. Skip until budget.

---

## CREDIT LIST (attribution required)

Dareful. Mazwai (CC clips). Videezy free. Videvo attribution clips. Vidsplay. Motion Places. CuteStockFootage. Free Stock Footage Archive. ESO. ESA/Hubble. Coverr. Wikimedia CC-BY files. YouTube/Vimeo CC-BY. Freepik free. Vecteezy free.

## NO-CREDIT LIST

Archive.org PD. NASA. LoC free-to-use. Smithsonian CC0. MotionElements PD. NPS (cite anyway). CDC (cite anyway). Mixkit. Pexels. Pixabay. Life of Vids. Splitshire. PikWizard. XStockvideo.

---

## GLOBAL RULES

- License per clip. Store license + source URL on every asset row.
- Never resell raw clips. Use inside edits only.
- People or private property in frame: need releases before ads. Mazwai says this explicitly. Applies everywhere.
- PD archives (Pond5 PD, PublicDomainFootage) say "believed PD". Verify before trusting.
- Ingest offline. Transcode with ffmpeg. Embed. Write ClipRecord. No runtime queries to any of these sites.
