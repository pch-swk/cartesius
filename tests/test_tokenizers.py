import pytest
from shapely.geometry import Polygon, LineString, Point

from cartesius.tokenizers import TransformerTokenizer


def test_transformer_tokenizer_single_polygon():
    tokenizer = TransformerTokenizer()
    p = Polygon([(0, 0), (0, 1), (1, 0), (0, 0)])

    result = tokenizer(p)

    assert result["mask"][0].tolist() == [True for _ in range(4)]
    assert result["polygon"][0].tolist() == [list(c) for c in p.boundary.coords]


@pytest.mark.parametrize("p", [LineString([(0, 0), (1, 1)]), Point((0, 0))])
def test_transformer_tokenizer_single_not_polygon(p):
    tokenizer = TransformerTokenizer()

    result = tokenizer(p)

    assert result["mask"][0].tolist() == [True for _ in range(len(p.coords))]
    assert result["polygon"][0].tolist() == [list(c) for c in p.coords]


def test_transformer_tokenizer_batched_polygons():
    tokenizer = TransformerTokenizer()
    p = [
        Polygon([(0, 0), (0, 1), (1, 0), (0, 0)]),
        Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]),
    ]

    result = tokenizer(p)

    assert result["mask"][0].tolist() == [True for _ in range(4)] + [False]
    assert result["polygon"][0].tolist() == [list(c) for c in p[0].boundary.coords] + [[0, 0]]
    assert result["mask"][1].tolist() == [True for _ in range(5)]
    assert result["polygon"][1].tolist() == [list(c) for c in p[1].boundary.coords]