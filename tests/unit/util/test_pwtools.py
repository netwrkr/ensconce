import string

from ensconce.util import pwtools

from tests import BaseTest

class PasswordtoolsTest(BaseTest):
    
    def test_generate(self):
        """ Basic password generation tests. """
        pw = pwtools.generate_password(255)
        self.assertEquals(255, len(pw))
        self.assertTrue(all([a in string.printable for a in pw]))
        
        pw = pwtools.generate_password(length=12, ascii_lower=True, ascii_upper=False, punctuation=False, digits=False)
        print pw
        self.assertTrue(all([a.islower() for a in pw]))
        self.assertTrue(all([a.isalpha() for a in pw]))
        
        pw = pwtools.generate_password(length=12, ascii_lower=True, ascii_upper=False, punctuation=False, digits=False)
        print pw
        self.assertTrue(all([a.islower() for a in pw]))
        self.assertTrue(all([a.isalpha() for a in pw]))
        
        pw = pwtools.generate_password(length=12, ascii_lower=False, ascii_upper=False, punctuation=False, digits=True)
        print pw
        self.assertTrue(all([a.isdigit() for a in pw]))
        
        pw = pwtools.generate_password(length=12, ascii_lower=True, ascii_upper=True, punctuation=False, digits=False)
        self.assertTrue(all([a.isalpha() for a in pw]))
        
        pw = pwtools.generate_password(length=12, ascii_lower=False, ascii_upper=False, punctuation=True, digits=False)
        self.assertTrue(all([not a.isalpha() for a in pw]))
        self.assertTrue(all([not a.isdigit() for a in pw]))
        
        with self.assertRaises(ValueError):
            pw = pwtools.generate_password(length=12, ascii_lower=False, ascii_upper=False, punctuation=False, digits=False)
            
        # Strip ambiguous
        pw = pwtools.generate_password(length=200, strip_ambiguous=True)
        self.assertFalse(any(c in pw for c in "LlOo0iI1"), "Did not expect to find any ambiguous characters in password.")
        