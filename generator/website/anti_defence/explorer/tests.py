from django.test import TestCase
from .models import Protein, ProteinDefences, ProteinPfams
import json

class ProteinModelTests(TestCase):
    def setUp(self):
        # Example JSON data as a string
        self.data = json.loads("""
        [
          {
            "defences": [
              {
                "defence_name": "AbiH",
                "link": "https://defensefinder.mdmlab.fr/wiki/defense-systems/abih"
              }
            ],
            "Protein source": {
              "name": "Vibrio phage 1.056.O.",
              "link": "https://www.ncbi.nlm.nih.gov/nuccore/MG592436.1"
            },
            "ID": "tlaloc",
            "Name": "Tlaloc",
            "MoA": "_",
            "MoA category": "unknown",
            "Defence subtype": "Vibrio cyclitrophicus superhost with AbiH",
            "Protein sequence": "VEVFLYLVHVHQLTYCLLMIYINCFQMYLYFLRRRGAIILSLLTGIDPRLQQFCTKSIF",
            "DOI": "10.1101/2024.06.14.598830",
            "Multicomponent system": null,
            "PDB": "_",
            "Structure": "tlaloc_model.cif",
            "Type of the 3D structure": "AlphaFold 3",
            "Existing Pfam domain": null,
            "Homologs from eukaryotic viruses": null
          }
        ]
        """)

    def test_create_protein_with_defence(self):
        item = self.data[0]
        protein = Protein.objects.create(
            id=item["ID"],
            name=item["Name"],
            moa=item["MoA"],
            moa_category=item["MoA category"],
            defence_subtype=item["Defence subtype"],
            sequence=item["Protein sequence"],
            doi=item["DOI"],
            multicomponent=item["Multicomponent system"],
            pdb=item["PDB"],
            pdb_filename=item["Structure"],
            structure_type=item["Type of the 3D structure"],
            existing_pfams=item["Existing Pfam domain"],
            euk_virus_homologs_filename=item["Homologs from eukaryotic viruses"],
            protein_source_name=item["Protein source"]["name"],
            protein_source_link=item["Protein source"]["link"]
        )

        self.assertEqual(protein.name, "Tlaloc")
        self.assertEqual(protein.structure_type, "AlphaFold 3")

        # Test defence
        defence = item["defences"][0]
        defence_obj = ProteinDefences.objects.create(
            protein=protein,
            defence_name=defence["defence_name"],
            defence_link=defence["link"]
        )

        self.assertEqual(defence_obj.defence_name, "AbiH")
        self.assertEqual(defence_obj.protein.id, "tlaloc")

    def test_str_methods(self):
        protein = Protein.objects.create(id="dummy", name="TestName")
        defence = ProteinDefences.objects.create(protein=protein, defence_name="SomeDefence")

        self.assertEqual(str(protein), "TestName")
        self.assertEqual(str(defence), "SomeDefence")

class ProteinPfamsModelTest(TestCase):
    def setUp(self):
        """Create a Protein instance for use in the tests."""
        self.protein = Protein.objects.create(
            id="protein_1",
            name="Test Protein",
            moa="Test MOA",
            moa_category="category",
            defence_subtype="type A",
            sequence="MKTAYIAKQRQISFVKSHFSRQDHLPGS",
            doi="10.1000/test",
            pdb="PDB1234",
            pdb_filename="test_model.pdb",
            structure_type="AlphaFold",
            protein_source_name="Test Source",
            protein_source_link="http://example.com"
        )

    def test_create_protein_pfams(self):
        """Test the creation of a ProteinPfams instance linked to a Protein."""
        protein_pfams = ProteinPfams.objects.create(
            protein=self.protein,
            pfam_name="PF00001",
            pfam_accession="PF00001",
            pfam_length=120,
            e_value=0.001,
            hmm_from=1,
            hmm_to=100,
            ali_from=1,
            ali_to=100,
            env_from=1,
            env_to=120,
        )
        self.assertEqual(protein_pfams.protein.id, self.protein.id)
        self.assertEqual(protein_pfams.pfam_name, "PF00001")
        self.assertEqual(protein_pfams.pfam_length, 120)
        self.assertAlmostEqual(protein_pfams.e_value, 0.001)

    def test_protein_pfams_string_representation(self):
        """Test the string representation of the ProteinPfams model."""
        protein_pfams = ProteinPfams.objects.create(
            protein=self.protein,
            pfam_name="PF00001",
            pfam_accession="PF00001",
            pfam_length=120,
            e_value=0.001,
            hmm_from=1,
            hmm_to=100,
            ali_from=1,
            ali_to=100,
            env_from=1,
            env_to=120,
        )
        self.assertEqual(str(protein_pfams), f"ProteinPfams ID: {protein_pfams.id}")
