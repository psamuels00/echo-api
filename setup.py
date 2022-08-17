from setuptools import setup

setup(
    name="echo-api",
    version="0.1.0",
    description="Mock API server with dynamic content capabilities",
    packages=["echoapi"],
    package_dir={"": "src"},
    url="https://github.com/psamuels00/echo-api",
    licence="Apache-2.0",
    author="Perrin Samuels",
    author_email="perrin.samuels@gmail.com",
    python_requires=">=3.7.3",
    # external packages as dependencies
    install_requires=[
        "flask == 2.2.2",
        "python-box == 6.0.2",
        "requests == 2.28.1",
    ],
    # for testing only
    extras_require={
        "test": [
            "black == 22.3.0",
            "coverage >= 5.5",
            "flake8 == 3.9.2",
            "pytest == 7.1.2",
        ],
    },
)
