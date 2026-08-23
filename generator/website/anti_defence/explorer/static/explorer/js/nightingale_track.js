import "@nightingale-elements/nightingale-sequence@latest";
import "@nightingale-elements/nightingale-track@latest";
import "@nightingale-elements/nightingale-manager@latest";
import "@nightingale-elements/nightingale-navigation@latest";

const pfamAnnotations = JSON.parse(document.getElementById('pfam-annotations-data').textContent);

const nightingaleTrackData = pfamAnnotations.map((pfam_annotation) => {
    return {
        "accession": pfam_annotation.accession,
        "start": pfam_annotation.env_start,
        "end": pfam_annotation.env_end,
        "color": stringToHexColor(pfam_annotation.accession),
        "locations": [{
            "fragments": [{
                "start": pfam_annotation.env_start,
                "end": pfam_annotation.env_end
            }]
        }]
    }
})

const nightingaleTrack = document.getElementById("nightingale_track");
if (nightingaleTrack) { // if there are pfam annotations
    nightingaleTrack.data = nightingaleTrackData;

    const nightingaleSequence = document.getElementById('nightingale_sequence');
    const nightingaleNavigation = document.getElementById('nightingale_navigation');

    nightingaleSequence.addEventListener('mouseover', (e) => {
        const { __data__: data } = e.target;
        
        if (data && data.position) {
            const position = data.position;
            nightingaleSequence.highlight = `${position}:${position}`;
            nightingaleNavigation.highlight = `${position}:${position}`;
            nightingaleTrack.highlight = `${position}:${position}`;
        }
    })
} 
