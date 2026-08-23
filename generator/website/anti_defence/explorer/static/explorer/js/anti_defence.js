const loadECODescriptions = () => {
  if (!window.tippy) return;

  tippy('.eco', {
    content: (reference) => {
      const short = reference.getAttribute('data-short') || '';
      const full = reference.getAttribute('data-full') || '';

      const container = document.createElement('div');

      // Short description always visible
      const shortDiv = document.createElement('div');
      shortDiv.textContent = short || reference.getAttribute('title') || '';
      container.appendChild(shortDiv);

      // Full description container (hidden initially)
      const fullDiv = document.createElement('div');
      fullDiv.textContent = full;
      fullDiv.style.display = 'none';
      fullDiv.style.marginTop = '6px';
      container.appendChild(fullDiv);

      // Toggle button
      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'eco-more';
      toggleBtn.type = 'button';
      toggleBtn.textContent = 'Show more';

      toggleBtn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        if (fullDiv.style.display === 'none') {
          fullDiv.style.display = 'block';
          this.textContent = 'Show less';
        } else {
          fullDiv.style.display = 'none';
          this.textContent = 'Show more';
        }
      });

      container.appendChild(toggleBtn);

      return container;
    },
    allowHTML: true,
    interactive: true,
    placement: 'top',
    delay: [100, 0],
  });
};

const delay = ms => new Promise(res => setTimeout(res, ms));

const getProteinId = () => {
  const path = window.location.pathname; // e.g. "/details/id/"
  const cleanParts = path.replace(/\/+$/, "").split("/");
  return cleanParts[cleanParts.length - 1];
}

const loadCorrectStructureChain = async () => {
  let sequence_select_box = document.querySelectorAll(".msp-sequence-select")[0];
  await delay(2000); // give time to load molecule

  let protein_id = getProteinId()

  let entity_box = sequence_select_box?.querySelectorAll(".msp-form-control")[2]; // Zero-based index

  if (entity_box && entity_box.tagName === "SELECT") {
    let options = Array.from(entity_box.options);

    let match = options.find(opt => {
        let parts = opt.textContent.split(":");
        let secondPart = parts.length > 1 ? parts[1].trim().toLowerCase() : "";
        return secondPart === protein_id;
    });

    if (match) {
        entity_box.value = match.value; // Set value as if user selected it
        match.dispatchEvent(new Event("click", { bubbles: true })); // Simulate user click
        entity_box.dispatchEvent(new Event("change", { bubbles: true })); // Trigger change event
    }
  }

};

const renderFeatures = (jsonData) => {
  if (!jsonData || !jsonData.sequence || !Array.isArray(jsonData.features)) {
      console.error('Invalid data structure for Feature Viewer:', jsonData);
      return;
  }

  const ft = new FeatureViewer.createFeature(jsonData.sequence,
      '#featuresContainer',
      {
          showAxis: true,
          showSequence: true,
          toolbar: true
      });

  jsonData.features.forEach(feature => {
      if (feature && feature.type && Array.isArray(feature.data)) {
          try {
              ft.addFeature(feature);
          } catch (error) {
              console.error('Error adding feature:', feature, error);
          }
      } else {
          console.warn('Invalid feature object:', feature);
      }
  });
};

const loadSecondaryStructureData = () => {
  let featureDataURL = document.getElementById('feature-data').dataset.url;
  fetch(featureDataURL)
      .then(response => {
          if (!response.ok) {
              throw new Error('Network response was not ok');
          }
          return response.json();
      })
      .then(data => {
          renderFeatures(data);
      })
      .catch(error => {
          console.error('Error fetching features JSON:', error);
      });
};

const stringToHexColor = (str) => {
  let color = '';

  if (str.length === 1) {
    const charCode = str.charCodeAt(0);

    const red = (charCode * 13) % 256;
    const green = (charCode * 17) % 256;
    const blue = (charCode * 19) % 256;

    const redHex = red.toString(16).padStart(2, '0');
    const greenHex = green.toString(16).padStart(2, '0');
    const blueHex = blue.toString(16).padStart(2, '0');

    color = `#${redHex}${greenHex}${blueHex}`;

    return color;
  }

  let hash = 0;

  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }

  color = '#';

  for (let i = 0; i < 3; i++) {
    const value = (hash >> (i * 8)) & 0xff;
    color += value.toString(16).padStart(2, '0');
  }

  return color;
};

const applyColorsToPfamItems = () => {
  const items = document.getElementsByClassName('pfam-item');
  for (let i = 0; i < items.length; i++) {
    const proteinPfamId = items[i].dataset.proteinpfam;
    const bgColor = stringToHexColor(proteinPfamId);
    const fourthCell = items[i].querySelector('td:nth-child(4)');
    if (fourthCell) {
      fourthCell.style.backgroundColor = bgColor;
    }
  }
};

const loadPfamsTable = () => {
  const pfamsTable = document.getElementById('pfams-table');
  if (pfamsTable) {
    $(pfamsTable).DataTable({
      dom: 'iftplr',
      language: {
        searchPlaceholder: 'Search',
        search: '',
      },
      drawCallback() {
        // Shorthand method definition
        applyColorsToPfamItems();
      },
    });

    applyColorsToPfamItems();
  }
};

const loadProteinSequenceContainer = () => {

    const proteinSequenceContainer = document.getElementById(
      'proteinSequenceContainer'
    );
    const positionMessage = document.getElementById('positionMessage');
    const proteinSequence = proteinSequenceContainer.textContent.trim();
    proteinSequenceContainer.innerHTML = '';
  
    /**
     * Load the sequence in the protein sequence viewer
     * @param {*} proteinSequence 
     * @param {*} proteinSequenceContainer 
     */
    const displaySequence = (proteinSequence, proteinSequenceContainer) => {
      for (let i = 0; i < proteinSequence.length; i++) {
        const span = document.createElement('span');
        span.textContent = proteinSequence[i];
        proteinSequenceContainer.appendChild(span);
      }
    };
  
    /**
     * Get the start and end from the query string
     * @returns { start and end}
     */
    const getStartAndEnd = () => {
      const urlParams = new URLSearchParams(window.location.search);
      const start = urlParams.get('start');
      const end = urlParams.get('end');
      return { start: start, end: end };
    };
  
    /**
     * Highlight a region of the protein
     * @param {*} proteinSequenceContainer the DOM element container 
     * @param {*} start start position 
     * @param {*} end end postition
     */
    const highlightRegion = (proteinSequenceContainer, start, end) => {
      for (let i = start; i <= end; i++) {
        const span = proteinSequenceContainer.children[i - 1];
        span.classList.add('highlight');
      }
    };
  
    /**
     * Event handlers
     *
     * */
    const updatePositionMessage = (position) => {
      positionMessage.textContent = `Amino acid position: ${position}`;
    };
    const updateCursorStyle = (cursorStyle) => {
      proteinSequenceContainer.style.cursor = cursorStyle;
    };
  
    const handleMouseOver = (event) => {
      if (event.target.tagName === 'SPAN') {
        const position = Array.from(
          proteinSequenceContainer.querySelectorAll('span')
        ).indexOf(event.target);
        updatePositionMessage(position + 1); // Add 1 to convert from 0-indexed position to 1-indexed
        const targetElement = event.target;
        targetElement.style.backgroundColor = '#ffc4c4';
      }
    };
  
    proteinSequenceContainer.addEventListener('mouseover', (event) => {
      updateCursorStyle('pointer');
      handleMouseOver(event);
    });
  
    proteinSequenceContainer.addEventListener('mousemove', handleMouseOver);
  
    proteinSequenceContainer.addEventListener('mouseout', (event) => {
      updatePositionMessage(' -');
      updateCursorStyle('auto');
      if (event.target.tagName === 'SPAN') {
        event.target.style.backgroundColor = '';
      }
    });
  
    /**
     * Render time!
     */
    displaySequence(proteinSequence, proteinSequenceContainer);
  
    const { start, end } = getStartAndEnd();
  
    if (start !== null && end !== null) {
      highlightRegion(proteinSequenceContainer, start, end);
    }
}

$(document).ready(() => {
  loadECODescriptions();
  loadCorrectStructureChain();
  loadSecondaryStructureData();
  loadPfamsTable();
  loadProteinSequenceContainer();
});
