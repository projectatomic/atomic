import unittest
from Atomic import diff
import copy


class FakeObj(object):
    def __init__(self):
        self.name = None
        self.inspect_data = None
        self.metadata_results = None


class TestMetaDiff(unittest.TestCase):

    ORANGE1 = ['navel', 'caracara']
    ORANGE2 = ORANGE1 + ['valencia']

    APPLES1 = {
        'red': ['fuji', 'gala', 'delicious'],
        'green': ['granny', 'golden']
    }

    APPLES2 = copy.deepcopy(APPLES1)
    APPLES2['red'] = APPLES1['red'] + ['jazz']
    APPLES2['green'] = []

    MARKET = {
        'apples': {
            'gala': 1965,
            'fuji': 1962,
            'delicious': 1914
        }
    }

    MARKET2 = {
        'apples': {
            'gala': 1965,
            'honeycrisp': 1991,
            'fuji': 1962
        }
    }

    FRUIT1= {
        "a": "apple",
        "b": "banana",
        "c": "carrot",
        "d": ["dragonfruit", "dates", "dill"],
        "e": {"egg": "EGG",
              "endive": 'ENDIVE'},
        "f": "figs"
    }

    FRUIT2 = copy.deepcopy(FRUIT1)
    FRUIT2['g'] = 'grapes'

    FRUIT3 = copy.deepcopy(FRUIT1)
    FRUIT3['o'] = ORANGE1
    FRUIT4 = copy.deepcopy(FRUIT1)
    FRUIT4['o'] = ORANGE2

    FRUIT5 = copy.deepcopy(FRUIT1)
    FRUIT5['o'] = APPLES1
    FRUIT6 = copy.deepcopy(FRUIT1)
    FRUIT6['o'] = APPLES2

    FRUIT7 = copy.deepcopy(FRUIT1)
    FRUIT7['r'] = MARKET
    FRUIT8 = copy.deepcopy(FRUIT1)
    FRUIT8['r'] = MARKET2

    EMPTY1 = {'foo': None}
    EMPTY2 = {}

    NEST_NONE1 = {'foo': {'bar': {'baz': 1}}}
    NEST_NONE2 = {'foo': {'bar': None}}

    def _create_image_list(self, *images):
        image_list = []
        for i in images:
            _image = FakeObj()
            _image.name = i
            _image.inspect_data = getattr(self, i)
            image_list.append(_image)
        return image_list

    @staticmethod
    def _get_results_metadata(images):
        return images[0].metadata_results, images[1].metadata_results

    def test_same(self):
        images = self._create_image_list('FRUIT1', 'FRUIT1')
        compare = diff.CompareMetaData(images)
        compare.compare()
        self.assertEqual(compare.img_obj1.metadata_results,
                         compare.img_obj2.metadata_results)

    def test_different_single(self):
        images = self._create_image_list('FRUIT1', 'FRUIT2')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, {})
        self.assertEqual(results2, {'g': 'grapes'})

    def test_list_same(self):
        images = self._create_image_list('FRUIT3', 'FRUIT3')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, results2)
        self.assertEqual(results1, {})

    def test_list_different(self):
        images = self._create_image_list('FRUIT3', 'FRUIT4')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, {'o': ['navel', 'caracara']} )
        self.assertEqual(results2, {'o': ['navel', 'caracara', 'valencia']})

    def test_nested_dict_same(self):
        images = self._create_image_list('FRUIT5', 'FRUIT5')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, results2)
        self.assertEqual(results1, {})

    def test_nested_dict_diff(self):
        images = self._create_image_list('FRUIT5', 'FRUIT6')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, {'o': {'green': ['granny', 'golden'], 'red': ['fuji', 'gala', 'delicious']}} )
        self.assertEqual(results2, {'o': {'green': [], 'red': ['fuji', 'gala', 'delicious', 'jazz']}})

    def test_nested2_dict_same(self):
        images = self._create_image_list('FRUIT7', 'FRUIT7')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, results2)
        self.assertEqual(results1, {})

    def test_nested2_dict_diff(self):
        images = self._create_image_list('FRUIT7', 'FRUIT8')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, {'r': {'apples': {'delicious': 1914}}})
        self.assertEqual(results2, {'r': {'apples': {'honeycrisp': 1991}}})

    def test_none_to_empty(self):
        images = self._create_image_list('EMPTY1', 'EMPTY2')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertNotEqual(results1, results2)
        self.assertEqual(results2, {})
        self.assertEqual(results1, {'foo': None})

    def test_nested_none(self):
        images = self._create_image_list('NEST_NONE1', 'NEST_NONE2')
        compare = diff.CompareMetaData(images)
        compare.compare()
        results1, results2 = self._get_results_metadata(images)
        self.assertEqual(results1, {'foo': {'bar': {'baz': 1}}})
        self.assertEqual(results2, {'foo': {'bar': None}})
