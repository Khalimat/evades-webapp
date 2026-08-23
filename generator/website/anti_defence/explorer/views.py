import re
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, Http404
from explorer.models import Protein, ProteinPfams, ProteinDefences

def index(request):
    num_proteins  = Protein.objects.count()
    first_protein = Protein.objects.first()

    context = {
        'num_proteins': num_proteins,
        'first_id': first_protein.id
    }

    return render(request, 'explorer/index.html', context)

def protein_list(request):
    proteins = Protein.objects.all()
    context = {
        'proteins': proteins,
    }
    return render(request, 'explorer/protein_list.html', context)

def safe_decode(blob):
    try:
        return blob.decode('utf-8') if blob else None
    except Exception as e:
        print(f"[safe_decode] Failed to decode blob: {e}")
        return None

def is_valid_protein_id(pk):
    return re.fullmatch(r'[A-Za-z0-9_-]+', pk) is not None

def details(request, pk):
    if not is_valid_protein_id(pk):
        messages.error(request, f"Invalid protein ID format: {pk}")
        return redirect('index')

    try:
        # Fetch Protein object
        protein = Protein.objects.get(pk=pk)
    except Protein.DoesNotExist:
        messages.error(request, f'Protein with ID {pk} does not exist.')
        return redirect('index')

    # Get all Pfam annotations for the protein
    protein_pfams = ProteinPfams.objects.filter(protein=protein)
    pfam_annotations = [{
        'name': pfam.pfam_name,
        'accession': pfam.pfam_accession.split(".")[0],
        'length': pfam.pfam_length,
        'hmm_start': pfam.hmm_from,
        'hmm_end': pfam.hmm_to,
        'ali_start': pfam.ali_from,
        'ali_end': pfam.ali_to,
        'env_start': pfam.env_from,
        'env_end': pfam.env_to,
        'evalue': pfam.e_value,
    } for pfam in protein_pfams]

    # Get defence annotations for the protein
    protein_defences = ProteinDefences.objects.filter(protein=protein)
    defences = [{
        'name': defence.defence_name,
        'link': defence.defence_link,
    } for defence in protein_defences]

    # Pass protein details to the template
    return render(request, 'explorer/details.html', {
        'id': protein.id,
        'name': protein.name,
        'moa': protein.moa,
        'evidence': protein.evidence,
        'moa_category': protein.moa_category,
        'defence_subtype': protein.defence_subtype,
        'sequence': protein.sequence,
        'doi': protein.doi,
        'multicomponent': protein.multicomponent,
        'pdb': protein.pdb,
        'pdb_blob': safe_decode(protein.pdb_blob),
        'is_cif': protein.pdb_filename.endswith('.cif') if protein.pdb_filename else False,
        'structure_type': protein.structure_type,
        'pred_secondary_structure_blob': safe_decode(protein.pred_secondary_structure_blob),
        'euk_virus_homologs_blob': safe_decode(protein.euk_virus_homologs_blob),
        'protein_source_name': protein.protein_source_name,
        'protein_source_link': protein.protein_source_link,
        'pfam_annotations': pfam_annotations,
        'defences': defences,
    })

def serve_blob_as_file(request, pk, column_name):
    protein_instance = get_object_or_404(Protein, pk=pk)
    blob_data = getattr(protein_instance, column_name)
    response = HttpResponse(blob_data, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment;'
    return response

def serve_euk_virus_homologs(request, pk):
    try:
        protein = Protein.objects.get(pk=pk)
        if protein.euk_virus_homologs_blob:
            return HttpResponse(protein.euk_virus_homologs_blob, content_type='text/html')
        else:
            raise Http404("No HTML content found.")
    except Protein.DoesNotExist:
        raise Http404("Protein not found.")