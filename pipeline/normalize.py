from sqlalchemy import text
from db.connection import get_engine

EXACT_OVERRIDES = {
    "Parque Las Heras, Barrio Norte": "Palermo",
}

CLEANUP = {
    "Barrio Norte": "Recoleta",
    "Centro": "San Nicolás",
    "Once": "Balvanera",
    "Congreso": "Balvanera",
    "Abasto": "Balvanera",
    "Parque Centenario": "Caballito",
    "Nuñez": "Núñez",
    "Villa Pueyrredon": "Villa Pueyrredón",
    "Villa Ortuzar": "Villa Ortúzar",
    "San Cristobal": "San Cristóbal",
    "Constitucion": "Constitución",
    "Agronomia": "Agronomía",
    "Boca": "La Boca",
    # Mercado Libre lists these sub-zones as barrios of their own
    "Palermo Hollywood": "Palermo",
    "Palermo Soho": "Palermo",
    "Palermo Chico": "Palermo",
    "Palermo Nuevo": "Palermo",
    "Palermo Viejo": "Palermo",
    "Las Cañitas": "Palermo",
    "Botánico": "Palermo",
    "Belgrano R": "Belgrano",
    "Belgrano C": "Belgrano",
    "Belgrano Chico": "Belgrano",
    "Belgrano Barrancas": "Belgrano",
    "Villa Gral. Mitre": "Villa General Mitre",
    "Santa Rita": "Villa Santa Rita",
    "Velez Sarsfield": "Vélez Sársfield",     # ML writes it with no accents at all
    "Villa Del Parque": "Villa del Parque",
    "Paternal": "La Paternal",
}

CITY_NAMES = {"Capital Federal", "CABA"}   # Argenprop switched to "X, CABA" in 2026


def clean_barrio(raw):
    """Barrio from a raw location string, whatever its shape:
    'Palermo Soho, Palermo' -> Palermo, 'Palermo, Capital Federal' -> Palermo,
    'Villa Real, CABA' -> Villa Real, 'CABELLO 3881, Palermo, Capital Federal'
    -> Palermo. The barrio is the last comma-separated part that isn't the city."""
    if raw in EXACT_OVERRIDES:
        return EXACT_OVERRIDES[raw]
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p and p not in CITY_NAMES]
    if not parts:
        return None
    candidate = parts[-1]
    return CLEANUP.get(candidate, candidate)


def main():
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT raw_neighborhood FROM listings WHERE raw_neighborhood IS NOT NULL")
        ).fetchall()

        for (raw,) in rows:
            cleaned = clean_barrio(raw)
            conn.execute(
                text("UPDATE listings SET neighborhood = :clean WHERE raw_neighborhood = :raw"),
                {"clean": cleaned, "raw": raw},
            )

    print("done")

if __name__ == "__main__":
    main()