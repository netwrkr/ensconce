import os.path
from setuptools import setup, find_packages

def get_requirements():
    reqsfile = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(reqsfile, 'r') as fp:
        return [req.strip() for req in fp if req.strip() != '' \
                and not req.strip().startswith('#')]

setup(
    name='ensconce',
    version='1.4',
    description='Ensconce Password Manager',
    license='BSD',
    install_requires=get_requirements(),  
    packages = find_packages('.'),
    package_data={'ensconce': ['templates/*.html']},
    include_package_data=True,
    test_suite='nose.collector',
    zip_safe=False,
    entry_points="""
    [console_scripts]
    ensconce-server=ensconce.cli:run_server
    """,
)
