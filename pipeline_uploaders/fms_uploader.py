import os
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.etree.ElementTree import tostring as xml_to_string

import lkaccess.contexts
import requests
from aicsfiles import FileManagementSystem
from aicsimageio import AICSImage
from lkaccess import LabKey, QueryFilter

"""
This is a superclass for uploading ot FMS

"""

OPTICAL_CONTROL_DIR = (
    "/allen/aics/microscopy/PRODUCTION/OpticalControl/ArgoLight/Argo_QC_Daily/"
)

OBJECTIVE_MAPPING = {
    20: '20x/0.80',
    40: '40x/1.2W', 
    63: '63x/1.2W', 
    100: '100x/1.25W', 
    101: '100x/1.46Oil', 
    44.83 : '44.83x/1.0W', 
    5 : '5x/0.12', 
    10 : '10x/0.45',

}


class FMSUploader:
    def __init__(self, file_path: str, file_type: str, metadata: dict, env="stg"):

        self.env = env
        self.file_path = Path(file_path)
        self.file_type = file_type
        self.metadata = metadata

    def upload(self):
        fms = FileManagementSystem(env=self.env)

        run_count = 0
        while run_count < 5:
            try:
                fms_file = fms.upload_file(
                    file_reference=self.file_path,
                    file_type=self.file_type,
                    metadata=self.metadata,
                )
                return fms_file.id
            except requests.exceptions.ReadTimeout:
                print("")
                run_count = run_count + 1
                continue
        return "Upload Failed"

    @staticmethod
    def get_labkey_metadata(barcode: str, env="stg"):

        if env == "prod":
            lk = LabKey(server_context=lkaccess.contexts.PROD)
        elif env == "stg":
            lk = LabKey(server_context=lkaccess.contexts.STAGE)
        else:
            raise Exception(f"Not a valid env. Must be [prod, stg]")

        my_rows = lk.select_rows_as_list(
            schema_name="microscopy",
            query_name="Plate",
            filter_array=[
                QueryFilter("Barcode", barcode),
            ],
        )

        plate_ID = my_rows[0]["PlateId"]

        r = requests.get(
            f"http://aics.corp.alleninstitute.org/metadata-management-service/1.0/plate/{plate_ID}",
            headers={
                "x-user-id": "brian.whitney"
            },  # this should change to a generic user
        )

        return r.json()

    @staticmethod
    def get_well_id(metadata_block: dict, row: int, col: int):  # TODO: Add typing to f

        wells = metadata_block["wells"]

        for well in wells:
            if (well["row"] == row) and (well["col"] == col):
                well_id = well["wellId"]
                return well_id
        if not well_id:
            raise Exception(
                f"The well at row {row} column {col} does not exist in labkey"
            )

    @staticmethod
    def get_imaging_date(file_path):  # TODO: move this to FMSUploader
        # path = './ImageDocument/Metadata/Information/Image/AcquisitionDateAndTime'
        file_img = AICSImage(file_path)

        with open("metadata.czi.xml", "w") as f:  # TODO: Make this not output a file
            f.write(xml_to_string(file_img.metadata, encoding="unicode"))
        tree = ET.parse("metadata.czi.xml")

        imaging_date = tree.findall(".//AcquisitionDateAndTime")[0].text
        os.remove("metadata.czi.xml")
        return imaging_date.split("T")[0]

    def get_QC_daily_path(
        system: str,  # Options are ZSD0, ZSD1, ZSD2, ZSD3, 3i0, 3i1
        objective: int,  # Options are 100, 63, 20
        date: int,  # Format is YYYYMMDD (e.g. 20220217)
        reference_directory: str = OPTICAL_CONTROL_DIR,  # use path to Argo_QC_daily
    ) -> Path:
        opt_cont_files = []
        for opt_dir in os.listdir(f"{reference_directory}/{system}"):
            folder_metadata = opt_dir.split("_")
            folder_metadata = [x.upper() for x in folder_metadata]
            if (
                all(x in folder_metadata for x in [system, f"{objective}X", str(date)])
                is True
            ):
                opt_conts = [
                    f
                    for f in os.listdir(f"{reference_directory}/{system}/{opt_dir}")
                    if f.endswith(".czi")
                ]
                for opt_cont in opt_conts:
                    opt_cont_files.append(
                        Path(f"{reference_directory}/{system}/{opt_dir}/{opt_cont}")
                    )

        if len(opt_cont_files) == 1:
            return Path(opt_cont_files[0])
        elif len(opt_cont_files) == 0:
            raise Exception(
                f"No files found with system: {system}, objective: {objective}, date: {date}"
            )
        else:
            print(
                f"Multiple files found with system: {system}, objective: {objective}, date: {date}. Printing all paths, and outputting the first found"
            )
            for i in opt_cont_files:
                print(i)
            return Path(opt_cont_files[0])

    def get_objective(file_path):
        # path = './ImageDocument/Metadata/Information/Image/AcquisitionDateAndTime'
        file_img = AICSImage(file_path)

        with open("metadata.czi.xml", "w") as f:  # TODO: Make this not output a file
            f.write(xml_to_string(file_img.metadata, encoding="unicode"))
        tree = ET.parse("metadata.czi.xml")

        objective = int(tree.findall(".//TotalMagnification")[
            0
        ].text) # TODO: This is not quite the right path
        os.remove("metadata.czi.xml")
        return objective / 10

    def get_system(file_path):
        # path = './ImageDocument/Metadata/Information/Image/AcquisitionDateAndTime'
        file_img = AICSImage(file_path)

        with open("metadata.czi.xml", "w") as f:  # TODO: Make this not output a file
            f.write(xml_to_string(file_img.metadata, encoding="unicode"))
        tree = ET.parse("metadata.czi.xml")

        system = tree.findall(".//FirstName")[
            0
        ].text  # TODO: This is not quite the right path
        # Delete file
        os.remove("metadata.czi.xml")
        return system
    
    def objective_mapping(objective : int):
        return OBJECTIVE_MAPPING(objective)