"""Farmer advisory content mapped to supported PlantVillage disease classes."""

_COMMON_PRACTICES = (
    "Scout crops regularly, keep field records, and maintain balanced nutrition "
    "and appropriate irrigation."
)
_COMMON_PREVENTION = (
    "Use healthy planting material, keep tools clean, and inspect crops regularly."
)
_TREATMENTS = {
    "healthy": "No treatment is indicated by this result. Avoid applying pesticides without a confirmed need.",
    "fungal": "Confirm the diagnosis locally. Use a locally registered fungicide only when recommended and follow its label.",
    "powdery_mildew": "Confirm the disease locally. If treatment is needed, use a locally approved product and follow its label.",
    "bacterial": "There may be no curative treatment. Confirm the diagnosis locally and consult a crop specialist before acting.",
    "rust": "Confirm the diagnosis locally. If treatment is needed, use a locally registered fungicide according to its label.",
    "viral": "There is no curative pesticide for plant viruses. Confirm the diagnosis and remove infected plants when advised.",
    "citrus_greening": "There is no cure for infected trees. Seek official local guidance on confirmation, vector management, and removal.",
    "esca": "Established trunk infections are difficult to cure. Consult a local viticulture specialist about pruning or removal.",
    "spider_mites": "Confirm mites are present before acting. Use locally registered controls only when needed and follow label directions.",
    "leaf_scorch": "Check for disease and environmental causes first. Seek local diagnosis; do not treat based on image results alone.",
}

DISEASE_GUIDANCE = {
    "healthy": {
        "cause": "No disease pattern was detected in the submitted image.",
        "symptoms": "The leaf resembles the healthy reference class; continue monitoring for changes.",
    },
    "fungal": {
        "cause": "Fungal pathogens can spread through infected residue, planting material, spores, and prolonged leaf wetness.",
        "symptoms": "Look for leaf spots, blighted areas, yellowing, or lesions with dark margins or visible growth.",
    },
    "powdery_mildew": {
        "cause": "Powdery mildew fungi spread by airborne spores and affect susceptible plants under favorable canopy conditions.",
        "symptoms": "Check for white powder-like patches, leaf curling, yellowing, or reduced plant vigor.",
    },
    "bacterial": {
        "cause": "Bacteria may spread through infected seed or transplants, splashing water, tools, hands, or plant debris.",
        "symptoms": "Look for water-soaked or angular spots, yellow halos, dark lesions, and possible leaf drop.",
    },
    "rust": {
        "cause": "Rust fungi produce spores that spread between host plants, often increasing under favorable humidity and mild temperatures.",
        "symptoms": "Look for small orange, reddish-brown, or dark raised pustules on leaves, sometimes with surrounding yellowing.",
    },
    "viral": {
        "cause": "Plant viruses often spread through infected planting material or insect vectors such as whiteflies and aphids.",
        "symptoms": "Possible signs include mosaic coloring, leaf curling, yellowing, stunting, and uneven growth; other stresses can look similar.",
    },
    "citrus_greening": {
        "cause": "Citrus greening is a bacterial disease spread mainly by the Asian citrus psyllid and infected planting material.",
        "symptoms": "Look for uneven blotchy yellowing, small upright shoots, and small, misshapen, poorly colored, or bitter fruit.",
    },
    "esca": {
        "cause": "Esca is a grapevine trunk disease associated with fungi entering through wounds or infected propagation material.",
        "symptoms": "Leaves may show interveinal striping or scorched margins; vines can decline and fruit may develop dark spots.",
    },
    "spider_mites": {
        "cause": "Spider mites are sap-feeding pests; hot, dry, dusty conditions and disruption of beneficial predators can favor outbreaks.",
        "symptoms": "Look for fine pale stippling, bronzing, webbing under leaves, and premature leaf drop.",
    },
    "leaf_scorch": {
        "cause": "Leaf scorch may result from fungal infection or environmental stress; this image result cannot confirm the exact cause.",
        "symptoms": "Leaf edges or patches may become brown, dry, and brittle, sometimes with yellow or reddish margins.",
    },
}

DISEASE_GUIDANCE_GROUPS = {
    "Apple - Apple scab": "fungal",
    "Apple - Black rot": "fungal",
    "Apple - Cedar apple rust": "rust",
    "Apple - healthy": "healthy",
    "Blueberry - healthy": "healthy",
    "Cherry (including sour) - Powdery mildew": "powdery_mildew",
    "Cherry (including sour) - healthy": "healthy",
    "Corn (maize) - Cercospora leaf spot Gray leaf spot": "fungal",
    "Corn (maize) - Common rust": "rust",
    "Corn (maize) - Northern Leaf Blight": "fungal",
    "Corn (maize) - healthy": "healthy",
    "Grape - Black rot": "fungal",
    "Grape - Esca (Black Measles)": "esca",
    "Grape - Leaf blight (Isariopsis Leaf Spot)": "fungal",
    "Grape - healthy": "healthy",
    "Orange - Haunglongbing (Citrus greening)": "citrus_greening",
    "Peach - Bacterial spot": "bacterial",
    "Peach - healthy": "healthy",
    "Pepper, bell - Bacterial spot": "bacterial",
    "Pepper, bell - healthy": "healthy",
    "Potato - Early blight": "fungal",
    "Potato - Late blight": "fungal",
    "Potato - healthy": "healthy",
    "Raspberry - healthy": "healthy",
    "Soybean - healthy": "healthy",
    "Squash - Powdery mildew": "powdery_mildew",
    "Strawberry - Leaf scorch": "leaf_scorch",
    "Strawberry - healthy": "healthy",
    "Tomato - Bacterial spot": "bacterial",
    "Tomato - Early blight": "fungal",
    "Tomato - Late blight": "fungal",
    "Tomato - Leaf Mold": "fungal",
    "Tomato - Septoria leaf spot": "fungal",
    "Tomato - Spider mites Two-spotted spider mite": "spider_mites",
    "Tomato - Target Spot": "fungal",
    "Tomato - Tomato Yellow Leaf Curl Virus": "viral",
    "Tomato - Tomato mosaic virus": "viral",
    "Tomato - healthy": "healthy",
}


def get_disease_guidance(disease_name):
    """Return advisory fields for a supported model label, if available."""
    group = DISEASE_GUIDANCE_GROUPS.get(disease_name.strip())
    if group is None:
        return None
    profile = DISEASE_GUIDANCE[group]
    return {
        **profile,
        "prevention": _COMMON_PREVENTION,
        "treatment": _TREATMENTS[group],
        "practices": _COMMON_PRACTICES,
    }
