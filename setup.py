from setuptools import find_packages, setup


setup(
    name="weather",
    version="0.1.0",
    packages=find_packages(include=["weather", "weather.*"]),
    install_requires=[
        "requests>=2.31,<3",
        "scipy>=1.11",
    ],
    extras_require={
        "dev": ["pytest>=8.0"],
        "ui": ["streamlit>=1.30", "plotly>=5.18", "pandas>=2.1"],
        "calibration": ["numpy>=1.24"],
    },
)
