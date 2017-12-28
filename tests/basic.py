# -*- coding: utf-8 -*-

from mga_graphql import MgaGraphQlSchemaConverter
import unittest
import os
import udm
from utilities import xme2mga


class BasicTestSuite(unittest.TestCase):
    """Basic test cases."""

    PATH_GME = r'C:\Program Files (x86)\GME'
    PATH_MGA = os.path.join(os.path.abspath(os.path.dirname(__file__)), r'models\sf.mga')
    PATH_XME = os.path.join(os.path.abspath(os.path.dirname(__file__)), r'models\sf.xme')
    PATH_UDM_XML = os.path.join(os.path.abspath(os.path.dirname(__file__)), r'models\SF.xml')

    @classmethod
    def setUpClass(cls):
        # Delete and reimport the SF model
        if os.path.exists(cls.PATH_MGA):
            os.remove(cls.PATH_MGA)
        xme2mga(cls.PATH_XME, cls.PATH_MGA)

        MgaGraphQlSchemaConverter(cls.PATH_UDM_XML)

        from schema import run_server, load_data
        d_models = load_data(cls.PATH_MGA,
                             cls.PATH_UDM_XML)
        run_server(d_models)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_mga_exists(self):
        self.assertTrue(os.path.exists(self.PATH_MGA))

    def test_truth(self):
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
