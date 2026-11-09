import unittest
from unittest.mock import patch
from studytrack.company_assistants import draft

class CompanyAssistants(unittest.TestCase):
    def test_role_specific_prompt_and_data(self):
        for role, marker in [('company', 'Paradigm Auditing'), ('racket', 'RackUnit')]:
            with patch('studytrack.company_assistants._generate', return_value='Draft for review') as call:
                self.assertEqual(draft(role, '  Build a proposal  '), 'Draft for review')
                self.assertEqual(call.call_args.args[0], {'requirements': 'Build a proposal'})
                self.assertIn(marker, call.call_args.args[1])
    def test_invalid_requests_do_not_call_api(self):
        with patch('studytrack.company_assistants._generate') as call:
            for role, request in [('unknown', 'request'), ('company', ''), ('racket', 'x'*12001)]:
                with self.assertRaises(ValueError): draft(role, request)
            call.assert_not_called()
    def test_provider_failure_is_visible(self):
        with patch('studytrack.company_assistants._generate', side_effect=ValueError('AI unavailable')):
            with self.assertRaisesRegex(ValueError, 'AI unavailable'): draft('company', 'Requirements')
