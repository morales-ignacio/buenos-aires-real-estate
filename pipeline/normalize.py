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
}

def clean_barrio(raw):
    if raw in EXACT_OVERRIDES:
        return EXACT_OVERRIDES[raw]
    a, b = raw.split(", ")
    candidate = b if b != "Capital Federal" else a
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