def test_dez_listas_consistentes():
    from app.clickup_client import AREA_LISTS, LIST_AREA, DONE_STATUS
    from app.tasks import AREAS
    assert len(AREA_LISTS) == 10 and len(set(AREA_LISTS.values())) == 10
    assert set(AREAS) == set(AREA_LISTS)
    assert {"Staging", "Trabalho", "Corpo", "Saúde Mental", "Responsabilidade",
            "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer"} == set(AREA_LISTS)
    assert LIST_AREA == {v: k for k, v in AREA_LISTS.items()}
    assert set(DONE_STATUS) == set(AREA_LISTS.values())   # todo list_id tem status de fechamento mapeado
