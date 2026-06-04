from pathlib import Path
from bs4 import BeautifulSoup

html = Path("samples/argenprop.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "html.parser")

price = soup.select_one("p.card__price")
box = price.find_parent(class_="card__details-box")
card = box.parent if box else price.parent

print("Card container:", card.name, card.get("class"))
print()

print("Links inside the card:")
for a in card.find_all("a", href=True)[:6]:
    print("  ", a.get("class"), "->", a["href"][:80])
anc = price.find_parent("a", href=True)
print("Ancestor link of price:", anc["href"][:80] if anc else "none")
print()

print("Classed elements inside the card (tag | class | text):")
for el in card.find_all(class_=True):
    text = el.get_text(" ", strip=True)[:50]
    print(f"  <{el.name}> {el.get('class')} | {text!r}")