from review import TAXONOMY, build_system_prompt


def test_prompt_variants_contain_all_definitions_verbatim():
    for variant in ("a", "b"):
        prompt = build_system_prompt(variant)
        for clause_type, definition in TAXONOMY.items():
            assert definition in prompt, f"variant {variant!r} missing {clause_type.value} definition"
