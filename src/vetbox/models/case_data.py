from typing import Any, Dict, Optional

class CaseData:
    """
    A class to store and manage veterinary case data.
    
    This class maintains a dictionary of symptoms and their associated data,
    where each symptom can have a presence status and multiple slots (attributes).
    
    Attributes:
        data (Dict[str, Dict[str, Any]]): The main storage for case data.
            Keys are symptom names, values are dictionaries containing 'present'
            status and any additional slot values.
    """
    
    def __init__(self):
        """Initialize an empty case data store."""
        self.data: Dict[str, Dict[str, Any]] = {}
    
    def add_symptom(self, symptom_name: str, present: bool) -> None:
        """
        Add or update a symptom's presence status.
        
        Args:
            symptom_name: The canonical name of the symptom
            present: Whether the symptom is present (True) or not (False)
        """
        if symptom_name not in self.data:
            self.data[symptom_name] = {"present": present}
        else:
            self.data[symptom_name]["present"] = present
    
    def add_slot(self, symptom_name: str, slot_name: str, value: Any) -> None:
        """
        Add or update a slot value for a specific symptom.
        
        Args:
            symptom_name: The canonical name of the symptom
            slot_name: The name of the slot to update
            value: The value to set for the slot
        """
        if symptom_name not in self.data:
            self.data[symptom_name] = {"present": None}
        self.data[symptom_name][slot_name] = value
    
    def get_symptom(self, symptom_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the data for a specific symptom.
        
        Args:
            symptom_name: The canonical name of the symptom
            
        Returns:
            The symptom's data dictionary if it exists, None otherwise
        """
        return self.data.get(symptom_name)
    
    def remove_symptom(self, symptom_name: str) -> None:
        """
        Remove a symptom and all its associated data from the case.
        
        Args:
            symptom_name: The canonical name of the symptom to remove
        """
        self.data.pop(symptom_name, None)
    
    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Convert the case data to a dictionary.
        
        Returns:
            A dictionary representation of the case data
        """
        return dict(self.data)
    
    def merge_extraction(self, extracted: Dict[str, Any]) -> None:
        """
        Merge new extracted data into the current case.
        
        This method updates existing symptoms and adds new ones from the
        extracted data. All slot values are updated with the new values.
        
        Args:
            extracted: A dictionary of extracted symptom data to merge.
                      Can be in format {"symptom": true/false} or {"symptom": {"present": true/false, ...}}
        """
        for symptom, value in extracted.items():
            if isinstance(value, bool):
                # Convert simple boolean to proper symptom format
                if symptom not in self.data:
                    self.data[symptom] = {"present": value}
                else:
                    self.data[symptom]["present"] = value
            elif isinstance(value, dict):
                # Handle dictionary format
                if symptom not in self.data:
                    self.data[symptom] = {}
                for k, v in value.items():
                    self.data[symptom][k] = v
            else:
                # Handle other types (strings, lists, etc.) as slot values
                if symptom not in self.data:
                    self.data[symptom] = {"present": None}
                self.data[symptom]["value"] = value