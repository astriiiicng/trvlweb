import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional
import requests
import uvicorn
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.cluster import KMeans
from openai import OpenAI

# ==========================================================
# ENV & OPENROUTER SETUP
# ==========================================================
# Load environment variables from project root .env and local .env
base_dir = os.path.dirname(os.path.abspath(__file__))
root_env = os.path.join(base_dir, "..", ".env")

if os.path.exists(root_env):
    load_dotenv(root_env)
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash-0731:free")

client = None
if OPENROUTER_API_KEY and OPENROUTER_API_KEY.strip() and OPENROUTER_API_KEY != "your_openrouter_api_key_here":
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY.strip()
        )
        print("[OK] OpenRouter API Client initialized.")
    except Exception as e:
        print("[ERROR] Gagal inisialisasi OpenRouter client:", e)
else:
    print("[WARNING] OPENROUTER_API_KEY tidak ditemukan atau masih placeholder. Menggunakan fallback AI cerdas.")


# ==========================================================
# FASTAPI
# ==========================================================
app = FastAPI(
    title="TripMate AI Travel Planner",
    description="TripMate Travel Planner with OpenRouter LLM & OpenStreetMap",
    version="10.0.0"
)


# ==========================================================
# REQUEST MODELS
# ==========================================================
class TripRequest(BaseModel):
    destination: str
    start_date: str
    end_date: str
    jumlah_orang: int = 1
    budget: float
    preferences: List[str]
    context: Optional[str] = ""

class RegenerateItemRequest(BaseModel):
    destination: str
    category: str
    current_place: str
    context: Optional[str] = ""


# ==========================================================
# CONSTANTS & MAPS
# ==========================================================
HEADERS = {
    "User-Agent": "TripMateTravelPlanner/10.0 (educational project)"
}

ALLOWED_CATEGORIES = {
    "pantai",
    "kuliner",
    "alam",
    "budaya",
    "hiburan"
}

CATEGORY_TAGS = {
    "pantai": [
        ("natural", "beach"),
        ("tourism", "beach")
    ],
    "kuliner": [
        ("amenity", "restaurant"),
        ("amenity", "cafe"),
        ("amenity", "fast_food"),
        ("amenity", "food_court")
    ],
    "alam": [
        ("tourism", "nature_reserve"),
        ("tourism", "viewpoint"),
        ("natural", "waterfall"),
        ("natural", "peak"),
        ("natural", "cliff"),
        ("natural", "wood"),
        ("leisure", "park")
    ],
    "budaya": [
        ("tourism", "museum"),
        ("tourism", "gallery"),
        ("tourism", "artwork"),
        ("historic", "monument"),
        ("historic", "castle"),
        ("historic", "fort"),
        ("historic", "archaeological_site"),
        ("historic", "memorial"),
        ("historic", "ruins"),
        ("amenity", "arts_centre")
    ],
    "hiburan": [
        ("tourism", "theme_park"),
        ("tourism", "zoo"),
        ("tourism", "aquarium"),
        ("leisure", "water_park"),
        ("leisure", "amusement_arcade"),
        ("amenity", "cinema"),
        ("amenity", "bowling_alley")
    ]
}

NOMINATIM_KEYWORDS = {
    "pantai": ["pantai", "beach"],
    "kuliner": ["restaurant", "restoran", "cafe", "rumah makan", "warung"],
    "alam": ["taman", "air terjun", "waterfall", "bukit", "viewpoint", "hutan", "nature reserve"],
    "budaya": ["museum", "benteng", "fort", "monumen", "galeri", "gallery", "heritage", "situs sejarah", "rumah adat", "cagar budaya"],
    "hiburan": ["taman hiburan", "theme park", "water park", "bioskop", "cinema", "wahana", "tempat rekreasi", "amusement"]
}

CATEGORY_DESCRIPTIONS = {
    "pantai": "Menikmati suasana pantai, laut, pesisir, dan pemandangan indah.",
    "kuliner": "Menikmati makanan khas lokal di restoran/tempat makan sekitar.",
    "alam": "Keindahan pemandangan alam, keasrian, dan suasana segar.",
    "budaya": "Mengenal sejarah, museum, situs budaya, dan nilai sejarah setempat.",
    "hiburan": "Wahana rekreasi, hiburan keluarga, dan aktivitas seru."
}

DEFAULT_CATEGORY_COST = {
    "pantai": 25000,
    "kuliner": 50000,
    "alam": 25000,
    "budaya": 20000,
    "hiburan": 45000
}

WORSHIP_WORDS = [
    "masjid", "mushalla", "mushola", "gereja", "church", "mosque", "surau", "vihara", "wihara", "pura"
]

NON_CULTURE_WORDS = [
    "sekolah", "school", "kampus", "university", "hospital", "rumah sakit", "clinic", "klinik",
    "bank", "minimarket", "supermarket", "pasar", "market", "warung", "restaurant", "cafe", "hotel", "kost", "perumahan"
]

OVERPASS_SERVERS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# ==========================================================
# UTILITAS FILTER & DEDUP
# ==========================================================
def normalize(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())

def is_worship_place(text):
    value = normalize(text)
    return any(word in value for word in WORSHIP_WORDS)

def is_valid_culture_place(name, tags_data=None):
    value = normalize(name)
    if is_worship_place(value):
        return False
    if any(word in value for word in NON_CULTURE_WORDS):
        return False

    tags_data = tags_data or {}
    valid_tag = (
        tags_data.get("tourism") in {"museum", "gallery", "artwork"}
        or tags_data.get("historic") in {"monument", "castle", "fort", "archaeological_site", "memorial", "ruins"}
        or tags_data.get("amenity") == "arts_centre"
    )
    if valid_tag:
        return True

    culture_words = ["museum", "benteng", "fort", "monumen", "monument", "galeri", "gallery", "heritage", "sejarah", "situs", "rumah adat", "cagar budaya"]
    return any(word in value for word in culture_words)

def is_valid_place(name, category, tags_data=None):
    if not name or len(str(name).strip()) < 3:
        return False
    if is_worship_place(name):
        return False
    if category == "budaya":
        return is_valid_culture_place(name, tags_data)
    return True

def remove_duplicates(places):
    seen = set()
    result = []
    for place in places:
        name = str(place.get("nama_tempat", "")).strip()
        clean = re.sub(r"[^a-z0-9]", "", name.lower())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(place)
    return result


# ==========================================================
# OPENSTREETMAP SEARCH & GEOFENCING
# ==========================================================
def is_within_bounding_box(lat: float, lon: float, bbox: Optional[List[float]]) -> bool:
    if not bbox or len(bbox) < 4:
        return True
    margin = 0.05
    south, north, west, east = bbox[0] - margin, bbox[1] + margin, bbox[2] - margin, bbox[3] + margin
    return south <= lat <= north and west <= lon <= east

DESTINATION_CACHE = {}

def search_destination(destination):
    clean_key = normalize(destination)
    if clean_key in DESTINATION_CACHE:
        return DESTINATION_CACHE[clean_key]

    params = {
        "q": f"{destination}, Indonesia",
        "format": "json",
        "limit": 5,
        "addressdetails": 1
    }
    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        if not data:
            return None

        destination_clean = normalize(destination)
        selected = data[0]
        for item in data:
            display = normalize(item.get("display_name", ""))
            if destination_clean in display:
                selected = item
                break

        bbox = None
        if "boundingbox" in selected and len(selected["boundingbox"]) >= 4:
            bbox = [float(b) for b in selected["boundingbox"]]

        result = {
            "lat": float(selected["lat"]),
            "lon": float(selected["lon"]),
            "display_name": selected.get("display_name", destination),
            "boundingbox": bbox
        }
        DESTINATION_CACHE[clean_key] = result
        return result
    except Exception as e:
        print("ERROR NOMINATIM DESTINATION:", e)
        return None

def search_places(lat, lon, category, bbox=None):
    tags = CATEGORY_TAGS.get(category, [])
    if not tags:
        return []

    radius = 15000
    query_parts = []
    for key, value in tags:
        for element_type in ("node", "way", "relation"):
            query_parts.append(f'{element_type}["{key}"="{value}"](around:{radius},{lat},{lon});')

    query = f"""
    [out:json][timeout:5];
    (
        {''.join(query_parts)}
    );
    out center tags;
    """

    for server in OVERPASS_SERVERS:
        try:
            response = requests.post(server, data=query, headers=HEADERS, timeout=3)
            response.raise_for_status()
            data = response.json()
            places = []

            for element in data.get("elements", []):
                tags_data = element.get("tags", {})
                name = tags_data.get("name")
                if not name:
                    continue

                name = str(name).strip()
                if not is_valid_place(name, category, tags_data):
                    continue

                element_lat = element.get("lat")
                element_lon = element.get("lon")
                if element.get("center"):
                    element_lat = element["center"].get("lat")
                    element_lon = element["center"].get("lon")

                if element_lat is None or element_lon is None:
                    continue

                e_lat, e_lon = float(element_lat), float(element_lon)
                if bbox and not is_within_bounding_box(e_lat, e_lon, bbox):
                    continue

                places.append({
                    "nama_tempat": name,
                    "kategori": category,
                    "deskripsi": CATEGORY_DESCRIPTIONS.get(category, "") + f" Rekomendasi lokasi di {name}.",
                    "estimasi_biaya": DEFAULT_CATEGORY_COST.get(category, 25000),
                    "lat": e_lat,
                    "lon": e_lon
                })

            places = remove_duplicates(places)
            if places:
                return places
        except Exception as e:
            print(f"Overpass error ({category}):", e)

    return []

def search_places_nominatim(destination, category, bbox=None):
    keywords = NOMINATIM_KEYWORDS.get(category, [])
    places = []

    for idx, keyword in enumerate(keywords[:3]):
        if idx > 0:
            import time
            time.sleep(0.3)

        params = {
            "q": f"{keyword}, {destination}, Indonesia",
            "format": "json",
            "limit": 10,
            "addressdetails": 1
        }
        try:
            response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
            if response.status_code == 429:
                break
            response.raise_for_status()
            data = response.json()

            for item in data:
                display_name = item.get("display_name", "")
                short_name = display_name.split(",")[0].strip()
                if not short_name or not is_valid_place(short_name, category, {}):
                    continue

                lat = item.get("lat")
                lon = item.get("lon")
                if lat is None or lon is None:
                    continue

                e_lat, e_lon = float(lat), float(lon)
                if bbox and not is_within_bounding_box(e_lat, e_lon, bbox):
                    continue

                places.append({
                    "nama_tempat": short_name,
                    "kategori": category,
                    "deskripsi": CATEGORY_DESCRIPTIONS.get(category, "") + f" Lokasi kunjungan di {short_name}.",
                    "estimasi_biaya": DEFAULT_CATEGORY_COST.get(category, 25000),
                    "lat": e_lat,
                    "lon": e_lon
                })

            if len(places) >= 10:
                break
        except Exception as e:
            print(f"Nominatim error ({category}):", e)

    return remove_duplicates(places)


# ==========================================================
# GEOGRAPHIC CLUSTERING (K-MEANS)
# ==========================================================
def cluster_places_by_days(all_places: List[dict], jumlah_hari: int) -> List[List[dict]]:
    """
    Mengelompokkan lokasi kandidat ke dalam kluster per hari berdasarkan kedekatan geografis (latitude & longitude)
    menggunakan algoritma K-Means.
    """
    if not all_places:
        return [[] for _ in range(jumlah_hari)]

    if len(all_places) <= jumlah_hari:
        # Jika tempat lebih sedikit dari jumlah hari, sebar tempat 1 per 1 per hari
        result = [[] for _ in range(jumlah_hari)]
        for i, place in enumerate(all_places):
            result[i % jumlah_hari].append(place)
        return result

    coords = np.array([[p["lat"], p["lon"]] for p in all_places])
    k = min(jumlah_hari, len(all_places))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(coords)

    clusters = [[] for _ in range(jumlah_hari)]
    for idx, label in enumerate(labels):
        target_day = label % jumlah_hari
        clusters[target_day].append(all_places[idx])

    return clusters


# ==========================================================
# OPENROUTER LLM ITINERARY GENERATOR
# ==========================================================
def generate_itinerary_with_llm(
    request: TripRequest,
    jumlah_hari: int,
    candidate_places: List[dict],
    start_date_obj: datetime
) -> Optional[dict]:
    """
    Mengirimkan kandidat tempat yang sudah ditemukan dan dikelompokkan ke OpenRouter LLM
    untuk menghasilkan susunan itinerary realistis beserta rincian biaya aktual.
    """
    if not client:
        return None

    # Ringkaskan daftar tempat per kategori untuk prompt
    candidates_summary = []
    for p in candidate_places[:50]:  # Dapatkan hingga 50 kandidat lokasi unik
        candidates_summary.append({
            "nama": p["nama_tempat"],
            "kategori": p["kategori"],
            "lat": p["lat"],
            "lon": p["lon"]
        })

    system_prompt = (
        "Anda adalah AI Travel Planner Indonesia yang sangat berpengalaman. "
        "Tugas Anda adalah menyusun rencana perjalanan wisata yang sangat logis, efisien, dan realistis di Indonesia. "
        "Selalu berikan estimasi harga tiket, kuliner, penginapan, dan transportasi secara realistis dalam Rupiah (IDR).\n"
        "WAJIB mengembalikan jawaban HANYA berupa JSON valid sesuai skema yang diminta, tanpa teks markdown tambahan di luar JSON."
    )

    user_prompt = f"""
Destinasi: {request.destination}
Tanggal Mulai: {request.start_date}
Jumlah Hari: {jumlah_hari} Hari
Jumlah Orang Rombongan: {request.jumlah_orang} Orang
Total Budget Rombongan: Rp {request.budget:,.0f} (PENTING: Ini adalah budget TOTAL untuk seluruh {request.jumlah_orang} orang!)
Kategori Favorit: {', '.join(request.preferences)}
Keterangan Tambahan / Keinginan Spesifik User: "{request.context if request.context else 'Tidak ada'}"

Kandidat Lokasi Wisata & Kuliner yang Ditemukan di Wilayah Tersebut:
{json.dumps(candidates_summary, ensure_ascii=False, indent=2)}

Petunjuk Penyusunan:
1. HITUNG BIAYA DENGAN MEMPERHITUNGKAN JUMLAH ORANG ({request.jumlah_orang} ORANG).
   - Tiket wisata dan makan harus dikalikan {request.jumlah_orang} orang.
   - Penginapan dihitung berdasarkan total sewa kamar untuk seluruh rombongan.
2. SUSUN REKOMENDASI UNTUK SETIAP HARI DARI HARI 1 HINGGA HARI {jumlah_hari}.
   - Setiap hari dari Hari 1 hingga Hari {jumlah_hari} HARUS diisi rekomendasi untuk SELURUH kategori favorit yang dipilih user: {', '.join(request.preferences)}.
   - DILARANG KERAS mengulang nama tempat yang sama di hari yang berbeda. Setiap hari HARUS mengunjungi destinasi dan tempat makan yang BERBEDA dan UNIK.
   - Jika kandidat lokasi di atas terbatas, Anda SANGAT DIPERBOLEHKEN menyuguhkan tempat wisata/kuliner populer nyata lainnya yang ada di {request.destination} agar jadwal setiap hari terisi penuh.
3. HANYA JIKA SUATU KATEGORI BENAR-BENAR TIDAK ADA DI {request.destination} (contoh: kategori pantai di wilayah pegunungan/tanpa pesisir):
   - JANGAN membuat nama tempat pantai palsu!
   - Kembalikan objek rekomendasi dengan:
     "nama_tempat": "Kategori [Nama Kategori] Tidak Tersedia",
     "deskripsi": "Kategori wisata [Nama Kategori] tidak ditemukan di wilayah ini.",
     "estimasi_biaya": 0,
     "is_available": false
4. Format JSON yang harus dikembalikan secara presisi:
{{
  "ringkasan": "Penjelasan singkat rencana perjalanan...",
  "estimasi_budget": {{
    "transportasi": 150000,
    "penginapan": 500000,
    "makan": 300000,
    "tiket_wisata": 100000,
    "total": 1050000,
    "sisa_budget": 450000,
    "status": "cukup"
  }},
  "itinerary": [
    {{
      "hari": 1,
      "tanggal": "{request.start_date}",
      "rekomendasi": [
        {{
          "kategori": "kuliner",
          "rekomendasi": "Nama Tempat Wisata / Kuliner",
          "nama_tempat": "Nama Tempat Wisata / Kuliner",
          "deskripsi": "Deskripsi singkat dan tips untuk tempat ini.",
          "estimasi_biaya": 140000,
          "is_available": true,
          "lat": -7.7956,
          "lon": 110.3695
        }}
      ]
    }}
  ]
}}
"""

    print("\n" + "="*50)
    print("PROMPT YANG DIKIRIM KE OPENROUTER LLM")
    print("="*50)
    print("SYSTEM PROMPT:\n", system_prompt)
    print("\nUSER PROMPT:\n", user_prompt)
    print("="*50 + "\n")

    models_to_try = [DEFAULT_MODEL, "deepseek/deepseek-chat:free", "google/gemini-2.5-flash", "openai/gpt-4o-mini"]

    for model in models_to_try:
        try:
            print(f"[LLM] Mengirim prompt ke OpenRouter LLM ({model})...")
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
                timeout=60.0
            )

            raw_content = completion.choices[0].message.content.strip()
            print("\n" + "="*50)
            print(f"RAW RESPONSE DARI OPENROUTER LLM ({model})")
            print("="*50)
            print(raw_content)
            print("="*50 + "\n")

            if raw_content.startswith("```"):
                raw_content = re.sub(r"^```[a-z]*\n?", "", raw_content)
                raw_content = re.sub(r"\n?```$", "", raw_content)

            parsed = json.loads(raw_content)
            if "itinerary" in parsed and is_instance_list(parsed["itinerary"]):
                print(f"[OK] Berhasil mendapatkan itinerary dari OpenRouter LLM ({model})")
                return parsed
        except Exception as e:
            print(f"[WARNING] Error OpenRouter LLM ({model}): {e}")

    return None

def is_instance_list(val):
    return isinstance(val, list)


# ==========================================================
# ENDPOINTS
# ==========================================================
@app.get("/")
def home():
    return {
        "status": "online",
        "message": "TripMate Travel Planner AI (OpenRouter + OpenStreetMap)",
        "mode": "OpenRouter LLM + OSM",
        "llm_active": client is not None,
        "categories": list(ALLOWED_CATEGORIES),
        "endpoint": "/plan"
    }

@app.post("/plan")
def plan_trip(request: TripRequest):
    print("\n========================================")
    print("TRIPMATE AI REQUEST")
    print("========================================")
    print("Destinasi :", request.destination)
    print("Mulai     :", request.start_date)
    print("Selesai   :", request.end_date)
    print("Budget    :", request.budget)
    print("Kategori  :", request.preferences)
    print("Konteks   :", request.context)

    # Validasi Kategori
    preferences = []
    for cat in request.preferences:
        c = normalize(cat)
        if c in ALLOWED_CATEGORIES and c not in preferences:
            preferences.append(c)

    if not preferences:
        return {
            "status": "error",
            "message": "Minimal pilih satu kategori wisata."
        }

    # Validasi Tanggal
    try:
        start = datetime.strptime(request.start_date, "%Y-%m-%d")
        end = datetime.strptime(request.end_date, "%Y-%m-%d")
    except ValueError:
        return {
            "status": "error",
            "message": "Format tanggal harus YYYY-MM-DD."
        }

    if end < start:
        return {
            "status": "error",
            "message": "Tanggal selesai tidak boleh sebelum tanggal mulai."
        }

    jumlah_hari = (end - start).days + 1
    if jumlah_hari > 30:
        return {
            "status": "error",
            "message": "Maksimal perjalanan adalah 30 hari."
        }

    # Search Destination Coordinate
    destination_info = search_destination(request.destination)
    if not destination_info:
        return {
            "status": "error",
            "message": f"Destinasi '{request.destination}' tidak ditemukan di OpenStreetMap."
        }

    # Search Candidate Places from OSM (Prioritize fast Nominatim search)
    bbox = destination_info.get("boundingbox")
    all_candidate_places = []
    places_by_category = {}

    for cat in preferences:
        # Nominatim search
        places = search_places_nominatim(request.destination, cat, bbox=bbox)
        if len(places) < 10:
            more_places = search_places_nominatim(request.destination, cat, bbox=None)
            places = remove_duplicates(places + more_places)

        if not places:
            places = search_places(destination_info["lat"], destination_info["lon"], cat, bbox=None)

        places_by_category[cat] = places
        all_candidate_places.extend(places)

    # Attempt OpenRouter LLM itinerary generation
    if client and all_candidate_places:
        llm_result = generate_itinerary_with_llm(request, jumlah_hari, all_candidate_places, start)
        if llm_result:
            return {
                "status": "success",
                "message": "Rencana perjalanan berhasil dibuat dengan AI OpenRouter.",
                "ringkasan": llm_result.get("ringkasan", f"Rencana perjalanan {jumlah_hari} hari di {request.destination}."),
                "trip": {
                    "destination": request.destination,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "jumlah_orang": request.jumlah_orang,
                    "budget": request.budget,
                    "preferences": preferences,
                    "context": request.context
                },
                "jumlah_hari": jumlah_hari,
                "estimasi_budget": llm_result.get("estimasi_budget", {}),
                "itinerary": llm_result.get("itinerary", [])
            }

    # Fallback to Geographic Clustering (K-Means) & Smart Heuristics if LLM unavailable or fails
    print("[INFO] Menggunakan fallback Clustering K-Means + Heuristik...")
    day_clusters = cluster_places_by_days(all_candidate_places, jumlah_hari)

    itinerary = []
    tiket_wisata = 0
    makan = 0
    used_places_global = set()

    for day_idx in range(jumlah_hari):
        tanggal = start + timedelta(days=day_idx)
        cluster_items = day_clusters[day_idx]
        rekomendasi = []

        for cat in preferences:
            cat_places = places_by_category.get(cat, [])
            
            if cat_places:
                # Cari tempat dalam kategori yang belum pernah digunakan di hari sebelumnya
                unused_in_cat = [p for p in cat_places if normalize(p["nama_tempat"]) not in used_places_global]
                
                # Jika seluruh tempat kandidat sudah pernah dipasang, gunakan pengulangan tempat dengan variasi index
                item = unused_in_cat[0] if unused_in_cat else cat_places[day_idx % len(cat_places)]
                used_places_global.add(normalize(item["nama_tempat"]))

                biaya_per_orang = DEFAULT_CATEGORY_COST.get(cat, 25000)
                biaya_total = biaya_per_orang * request.jumlah_orang
                if cat == "kuliner":
                    makan += biaya_total
                else:
                    tiket_wisata += biaya_total

                desc = item["deskripsi"]
                if request.context:
                    desc += f" (Disesuaikan dengan konteks: {request.context})"

                rekomendasi.append({
                    "kategori": cat,
                    "rekomendasi": item["nama_tempat"],
                    "nama_tempat": item["nama_tempat"],
                    "deskripsi": desc,
                    "estimasi_biaya": biaya_total,
                    "is_available": True,
                    "lat": item["lat"],
                    "lon": item["lon"]
                })
            else:
                # Kategori wisata benar-benar tidak tersedia di wilayah ini (0 tempat ditemukan)
                rekomendasi.append({
                    "kategori": cat,
                    "rekomendasi": f"Kategori {cat.capitalize()} Tidak Tersedia",
                    "nama_tempat": f"Kategori {cat.capitalize()} Tidak Tersedia",
                    "deskripsi": f"Wisata kategori '{cat}' tidak ditemukan di wilayah {request.destination}.",
                    "estimasi_biaya": 0,
                    "is_available": False,
                    "lat": destination_info["lat"],
                    "lon": destination_info["lon"]
                })

        itinerary.append({
            "hari": day_idx + 1,
            "tanggal": tanggal.strftime("%Y-%m-%d"),
            "rekomendasi": rekomendasi
        })

    transportasi = jumlah_hari * 75000
    kamar = max(1, (request.jumlah_orang + 1) // 2)
    jumlah_malam = max(jumlah_hari - 1, 0)
    penginapan = kamar * 250000 * jumlah_malam
    total = transportasi + penginapan + makan + tiket_wisata
    sisa = request.budget - total

    return {
        "status": "success",
        "message": "Rencana perjalanan berhasil dibuat.",
        "ringkasan": f"Rencana perjalanan {jumlah_hari} hari di {request.destination} untuk {request.jumlah_orang} orang.",
        "trip": {
            "destination": request.destination,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "jumlah_orang": request.jumlah_orang,
            "budget": request.budget,
            "preferences": preferences,
            "context": request.context
        },
        "jumlah_hari": jumlah_hari,
        "estimasi_budget": {
            "transportasi": transportasi,
            "penginapan": penginapan,
            "makan": makan,
            "tiket_wisata": tiket_wisata,
            "total": total,
            "sisa_budget": sisa,
            "status": "cukup" if sisa >= 0 else "melebihi_budget"
        },
        "itinerary": itinerary
    }

def generate_single_alternative_with_llm(destination: str, category: str, current_place: str) -> Optional[dict]:
    if not client:
        return None
    prompt = f"""
    Berikan 1 tempat alternatif nyata untuk kategori '{category}' di {destination}, Indonesia yang BERBEDA dari '{current_place}'.
    Jika di {destination} tidak ada tempat untuk kategori '{category}' yang relevan (misal pantai di daerah pegunungan), kembalikan nama_tempat: "Kategori {category.capitalize()} Tidak Tersedia", deskripsi: "Kategori {category} tidak ditemukan di wilayah ini.", estimasi_biaya: 0, is_available: false.

    Format JSON:
    {{
        "kategori": "{category}",
        "rekomendasi": "Nama Tempat",
        "nama_tempat": "Nama Tempat",
        "deskripsi": "Deskripsi singkat alternatif tempat ini.",
        "estimasi_biaya": 25000,
        "is_available": true,
        "lat": null,
        "lon": null
    }}
    """
    models_to_try = ["google/gemini-2.5-flash", DEFAULT_MODEL, "openai/gpt-4o-mini"]
    for model in models_to_try:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Anda adalah AI Travel Planner Indonesia yang akurat."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
                timeout=10.0
            )
            content = completion.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```[a-z]*\n?", "", content)
                content = re.sub(r"\n?```$", "", content)
            return json.loads(content)
        except Exception as e:
            print(f"[LLM ALT ERROR ({model})]", e)
    return None

@app.post("/regenerate")
@app.post("/regenerate/")
def regenerate_item(request: RegenerateItemRequest):
    """
    Endpoint untuk mencari rekomendasi alternatif satu lokasi (Fitur Ganti Tempat)
    """
    print(f"[REGENERATE] Request for: '{request.current_place}' in {request.destination} ({request.category})")
    try:
        dest_info = search_destination(request.destination)
        bbox = dest_info.get("boundingbox") if dest_info else None

        places = search_places_nominatim(request.destination, request.category, bbox=bbox)
        if len(places) < 3:
            more_places = search_places_nominatim(request.destination, request.category, bbox=None)
            places = remove_duplicates(places + more_places)

        current_clean = normalize(request.current_place)
        alternatives = [p for p in places if normalize(p["nama_tempat"]) != current_clean]

        if alternatives:
            new_place = alternatives[0]
            return {
                "status": "success",
                "item": {
                    "kategori": request.category,
                    "rekomendasi": new_place["nama_tempat"],
                    "nama_tempat": new_place["nama_tempat"],
                    "deskripsi": new_place["deskripsi"],
                    "estimasi_biaya": new_place["estimasi_biaya"],
                    "is_available": True,
                    "lat": new_place["lat"],
                    "lon": new_place["lon"]
                }
            }

        # LLM fallback jika tersedia
        if client and dest_info:
            llm_alt = generate_single_alternative_with_llm(request.destination, request.category, request.current_place)
            if llm_alt:
                if llm_alt.get("lat") is None and dest_info:
                    llm_alt["lat"] = dest_info["lat"]
                    llm_alt["lon"] = dest_info["lon"]
                return {
                    "status": "success",
                    "item": llm_alt
                }

        # Fallback jika tidak ada tempat alternatif
        return {
            "status": "success",
            "item": {
                "kategori": request.category,
                "rekomendasi": f"Kategori {request.category.capitalize()} Tidak Tersedia",
                "nama_tempat": f"Kategori {request.category.capitalize()} Tidak Tersedia",
                "deskripsi": f"Tidak ditemukan alternatif tempat lain untuk kategori '{request.category}' di {request.destination}.",
                "estimasi_biaya": 0,
                "is_available": False,
                "lat": dest_info["lat"] if dest_info else None,
                "lon": dest_info["lon"] if dest_info else None
            }
        }
    except Exception as e:
        print("[REGENERATE EXCEPTION]", e)
        return {
            "status": "error",
            "message": f"Gagal mengambil tempat alternatif: {str(e)}"
        }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8002))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
