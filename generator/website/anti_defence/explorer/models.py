from django.db import models

class Protein(models.Model):
    id                            = models.TextField(primary_key=True)
    name                          = models.TextField(null=True)
    moa                           = models.TextField(null=True)
    evidence                      = models.TextField(null=True)
    moa_category                  = models.TextField(null=True)
    defence_subtype               = models.TextField(null=True)
    sequence                      = models.TextField(null=True)
    doi                           = models.TextField(null=True)
    multicomponent                = models.TextField(null=True)
    pdb                           = models.TextField(null=True)
    pdb_filename                  = models.TextField(null=True)
    pdb_blob                      = models.BinaryField(null=True)
    structure_type                = models.TextField(null=True)
    existing_pfams                = models.TextField(null=True)
    euk_virus_homologs_filename   = models.TextField(null=True)
    euk_virus_homologs_blob       = models.BinaryField(null=True)
    protein_source_name           = models.TextField(null=True)
    protein_source_link           = models.TextField(null=True)
    pred_secondary_structure_file = models.TextField(null=True)
    pred_secondary_structure_blob = models.BinaryField(null=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        db_table = 'protein'

class ProteinDefences(models.Model):
    id = models.AutoField(primary_key=True)
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE)
    defence_name = models.TextField(null=True)
    defence_link = models.TextField(null=True)

    def __str__(self):
        return f"ProteinDefences ID: {self.id}"
    
    def __str__(self):
        return f"{self.defence_name}"

    class Meta:
        db_table = 'protein_defence'

class ProteinPfams(models.Model):
    id = models.AutoField(primary_key=True)
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE)
    pfam_name = models.TextField(null=False)
    pfam_accession = models.TextField(null=False)
    pfam_length = models.IntegerField(null=False)
    e_value = models.FloatField(null=False)
    hmm_from = models.IntegerField(null=False)
    hmm_to = models.IntegerField(null=False)
    ali_from = models.IntegerField(null=False)
    ali_to = models.IntegerField(null=False)
    env_from = models.IntegerField(null=False)
    env_to = models.IntegerField(null=False)

    def __str__(self):
        return f"ProteinPfams ID: {self.id}"

    class Meta:
        db_table = 'protein_pfams'
