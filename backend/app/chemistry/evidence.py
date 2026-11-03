"""Source-linked research notes, not validated formulation rules."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str
    url: str = Field(pattern=r"^https://")
    source_type: Literal["primary_research", "manufacturer_guidance"]
    access_level: str
    finding: str
    conditions: str
    limitation: str
    checked_on: str = "2026-11-03"
    review_status: Literal["literature_draft"] = "literature_draft"


SOURCES = (
    Evidence(
        id="EVONIK-H2O2-STABILITY",
        title="Evonik — Stability & Decomposition",
        url="https://www.evonik.com/en/company/businesslines/ao/products-and-services/"
        "hydrogen-peroxide/general-information/stability-and-decomposition.html",
        source_type="manufacturer_guidance",
        access_level="Halaman teknis produsen dibaca langsung.",
        finding="Suhu, pH, dan kontaminan termasuk ion logam memengaruhi dekomposisi H2O2.",
        conditions="Panduan penyimpanan dan penanganan larutan H2O2 komersial.",
        limitation="Bukan uji formula parfum LKPI; tidak menetapkan ambang pH, dosis penstabil, "
        "atau umur simpan formula akhir. Tidak berlaku otomatis untuk semua peroksida organik.",
    ),
    Evidence(
        id="DOI:10.1039/C8RE00094H",
        title="Resul et al. (2018) — Epoxidation of limonene with a tungsten-based catalyst",
        url="https://eprints.ncl.ac.uk/252152",
        source_type="primary_research",
        access_level="Abstrak dan metadata pada repositori penulis dibaca langsung.",
        finding="Studi melaporkan epoksidasi limonene dengan H2O2 menggunakan katalis tungsten.",
        conditions="Proses sintesis pada 323 K, sistem tanpa pelarut, dengan katalis dan "
        "pengaturan keasaman; bukan pengujian penyimpanan disinfektan.",
        limitation="Contoh reaktivitas limonene berkatalis, bukan bukti semua alkena akan "
        "terdegradasi pada kondisi produk LKPI. Tidak menghasilkan skor risiko kuantitatif.",
    ),
    Evidence(
        id="DOI:10.1002/ffj.3210",
        title="Kern et al. (2014) — Stability of limonene in fragranced products",
        url="https://onlinelibrary.wiley.com/doi/10.1002/ffj.3210",
        source_type="primary_research",
        access_level="Teks artikel, metode, dan hasil stabilitas dibaca langsung.",
        finding="Penelitian melaporkan kestabilan limonene pada parfum hidroalkohol yang diuji "
        "selama sembilan bulan.",
        conditions="Matriks parfum hidroalkohol; bukan formula disinfektan H2O2.",
        limitation="Menunjukkan pentingnya matriks. Tidak membuktikan kompatibilitas limonene "
        "dengan H2O2, keamanan inhalasi, atau keberhasilan bahan penstabil pada formula LKPI.",
    ),
    Evidence(
        id="DOI:10.1039/C5RA02234G",
        title="Hu et al. (2015) — Catalytic oxidation of aldehydes and ketones with H2O2",
        url="https://pubs.rsc.org/en/content/articlelanding/2015/ra/c5ra02234g",
        source_type="primary_research",
        access_level="Abstrak penerbit dari hasil pencarian; akses langsung mengembalikan 403.",
        finding="Abstrak melaporkan oksidasi aldehida menjadi asam karboksilat dengan H2O2 "
        "dalam sistem berkatalis.",
        conditions="Katalis Co4HP2Mo15V3O62 dalam cairan ionik [TEBSA][BF4]. "
        "Detail metode lengkap belum ditelaah.",
        limitation="Tidak dapat dipindahkan langsung ke setiap aldehida parfum dalam "
        "disinfektan air tanpa katalis tersebut.",
    ),
    Evidence(
        id="DOI:10.1039/C8RE00085A",
        title="Roberts et al. (2018) — Au-catalyzed oxidation of alcohols in continuous flow",
        url="https://pubs.rsc.org/en/content/articlelanding/2018/re/c8re00085a",
        source_type="primary_research",
        access_level="Abstrak penerbit dari hasil pencarian; akses langsung mengembalikan 403.",
        finding="Alkohol primer yang diteliti mengalami oksidasi dengan H2O2 pada katalis Au/TiO2.",
        conditions="Aliran kontinu dalam metanol; hasil bergantung pada jenis substrat "
        "dan kondisi reaksi.",
        limitation="Bukan bukti semua alkohol tidak kompatibel. Pola alkohol generik juga "
        "mencakup alkohol sekunder/tersier yang tidak dicakup klaim abstrak ini.",
    ),
    Evidence(
        id="DOI:10.1039/C9RA02021G",
        title="RSC Advances (2019) — Catalytic hydroxylation of phenol with H2O2",
        url="https://pubs.rsc.org/en/content/articlehtml/2019/ra/c9ra02021g",
        source_type="primary_research",
        access_level="Cuplikan teks penerbit dari hasil pencarian; akses langsung 403.",
        finding="Penelitian mempelajari hidroksilasi fenol dengan H2O2 pada katalis Cu-apatite.",
        conditions="Sistem berair berkatalis; pengaruh suhu dan rasio reaktan diteliti.",
        limitation="Studi fenol berkatalis tidak otomatis berlaku untuk seluruh turunan "
        "fenolik parfum atau kondisi penyimpanan formula LKPI.",
    ),
)
BY_ID = {source.id: source for source in SOURCES}


def research_note(source: Evidence) -> str:
    """Keep each retrieval chunk self-contained about evidence limitations."""
    return (
        f"CATATAN LITERATUR DRAFT BAYLab — bukan teks asli artikel atau validasi ahli.\n"
        f"Judul: {source.title}\nSumber: {source.id}\nURL: {source.url}\n"
        f"Diperiksa: {source.checked_on}. Cakupan akses: {source.access_level}\n"
        f"Temuan: {source.finding}\nKondisi: {source.conditions}\n"
        f"Batas penerapan: {source.limitation}\n"
        "Tidak menetapkan formula, tingkat risiko, dosis, keamanan, atau efikasi antimikroba."
    )
