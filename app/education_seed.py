"""Public safety explanations available even when demonstration data is disabled."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import EducationalContent

ARTICLES = [
    (
        "TEMPESTADE",
        "Tempestades severas",
        (
            "Tempestades convectivas podem produzir raios, rajadas fortes, granizo e chuva "
            "intensa. Busque uma construção resistente, afaste-se das janelas e não se "
            "abrigue sob árvores. Acompanhe os avisos oficiais e as orientações da Defesa "
            "Civil."
        ),
        "storm",
    ),
    (
        "TORNADO",
        "Tornados: procure abrigo",
        (
            "Um tornado é uma coluna de ar em rotação que liga uma nuvem de tempestade ao "
            "solo. Vá ao piso mais baixo de uma construção resistente, em um cômodo interno "
            "sem janelas. Proteja a cabeça e o pescoço. Não saia para observar ou filmar o "
            "fenômeno."
        ),
        "tornado",
    ),
    (
        "GRANIZO",
        "Granizo: mantenha distância das janelas",
        (
            "Granizo são pedras de gelo que se formam em nuvens de tempestade. Elas podem "
            "ferir pessoas e danificar telhados e veículos. Permaneça em local coberto e "
            "resistente, longe de vidros. Aguarde o fim da tempestade antes de verificar "
            "danos."
        ),
        "hail",
    ),
    (
        "VENTO",
        "Rajadas de vento",
        (
            "Ventos intensos podem derrubar árvores, destelhar construções e lançar objetos. "
            "Procure abrigo resistente e mantenha distância de árvores, postes e estruturas "
            "frágeis. Não toque em cabos caídos; avise os serviços de emergência."
        ),
        "wind",
    ),
    (
        "ALAGAMENTO",
        "Chuva intensa e alagamentos",
        (
            "Chuvas intensas podem causar enxurradas, alagamentos e deslizamentos. Não "
            "atravesse água em movimento ou ruas alagadas a pé ou de veículo. Procure um "
            "local seguro, siga as rotas indicadas pela Defesa Civil e ligue 199 em caso de "
            "risco."
        ),
        "rain",
    ),
]


def ensure_education(db):
    for key, title, body, illustration in ARTICLES:
        source_key = f"EDU-{key}"
        if db.scalar(
            select(EducationalContent.id).where(EducationalContent.source_key == source_key)
        ):
            continue
        db.add(
            EducationalContent(
                source_key=source_key,
                title=title,
                body=body,
                media_url=f"/assets/img/safety-{illustration}.svg",
                reference_url="https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil",
                published_at=datetime.now(UTC),
            )
        )
