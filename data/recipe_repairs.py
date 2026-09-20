"""Fill missing quantities in an untouched legacy recipe, never overwrite edits."""
GREEK_SALAD_ORIGINAL = {
    'name': 'Greek Salad',
    'description': 'A crisp salad with cucumber, tomatoes, olives, and feta.',
    'category': 'Salads', 'cooking_time': 15, 'difficulty': 'Easy', 'servings': 2,
    'ingredients': 'cucumber\ntomatoes\nfeta\nolives\nred onion\nolive oil',
    'instructions': 'Chop the vegetables.\nAdd feta and olives.\nDress with olive oil.\nToss gently and serve.',
    'image_url': None,
}
GREEK_SALAD_COMPLETE = {
    **GREEK_SALAD_ORIGINAL,
    'description': 'Свежий салат с хрустящими овощами, фетой и оливковой заправкой.',
    'difficulty': 'Легко',
    'ingredients': 'огурец — 1 шт.\nпомидоры — 2 шт.\nфета — 100 г\nоливки без косточек — 60 г\nкрасный лук — ½ шт.\nоливковое масло — 2 ст. л.\nлимонный сок — 1 ст. л.\nсушёный орегано — ½ ч. л.\nсоль — по вкусу',
    'instructions': 'Вымойте и обсушите овощи. Огурец нарежьте полукружьями, помидоры — дольками.\nНарежьте лук тонкими перьями, фету — кубиками по 1,5 см. С оливок слейте рассол.\nСмешайте масло с лимонным соком и орегано.\nСоедините овощи и оливки, полейте заправкой и аккуратно перемешайте.\nСверху разложите фету. Попробуйте перед добавлением соли и подавайте сразу.',
}
