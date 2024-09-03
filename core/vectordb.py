from qdrant_client import QdrantClient,models
from qdrant_client.models import  PointStruct
from data.types import Data

class QdrantDB:

    def __init__(self, host: str = "http://localhost", port:str=6333, verbose=True):
            self.url = f"{host}:{port}"
            self.client = self._create_client()
            self.verbose = verbose

    
    def _create_client(self) -> 'QdrantClient':
        try:
            return QdrantClient(url=self.url)
        except Exception as e:
            print(f"Failed to create QdrantClient: {e}")
            return None
        
    def create_collection(self,collection_name:str,**kwargs):
        if not self.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                **kwargs
            )

    def collection_exists(self,collection_name):
        return self.client.collection_exists(collection_name)
    
    def search_point(self,collection_name,id):
        res = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="parent_id",
                            match=models.MatchValue(value=id),
                        ),
                    ]
                ),
            )
        
        res = res[0] # res is a tuple we need the first element 
        #each parent_id in db is unique so it only return the one point in a collection
        return res[0]
            
    def get_payload(self,data:Data):
        payload = {}
        payload['text'] = data.content
        payload['parent_id'] = data.id
        for key, value in data.metadata.items():
            payload[key] = value
        return payload
    
    def process_data(self,data:Data):

        points = []
        for data in data:
            point_id = data.metadata.get('chunk_id', data.id)
            vectors = {}
           
            if data.vectors != []:
               vectors["text_dense_vec"] = data.vectors

            payload = self.get_payload(data)
            point = PointStruct(id=point_id,vector=vectors,payload=payload)
            points.append(point)

        return points
    
    
    def upload_points(self, collection_name, vectors, batch_size=64):
        try:
            operation_info = self.client.upload_points(
                collection_name=collection_name,
                points=vectors,
                batch_size=batch_size,
                wait=True
            )
            return operation_info
        except Exception as ex:
             raise Exception(f"Exception while inserting point in {collection_name}")
    

    def as_indexer(self,data:Data,collection_name = None):

        if collection_name is None or not self.client.collection_exists(collection_name):
            raise Exception(f"Collection {collection_name} does not exist")
        
        try:
            if not isinstance(data, list):
                data = [data]

            data=self.process_data(data)
            self.upload_points(collection_name, data)
        except Exception as ex:
            raise ex
        
    def as_retriever(self,query:Data,collection_name:str, top_k:int=5):
        if collection_name is None or not self.client.collection_exists(collection_name):
            raise Exception(f"Collection {collection_name} does not exist")

        req = models.SearchRequest(
                            vector=models.NamedVector(
                                name='text_dense_vec',
                                vector=query.vectors
                            ),
                            limit=top_k,
                            with_payload=True,
                        )
        res = self.client.search_batch(
                    collection_name=collection_name,
                    requests=[req])
        
        context = []
        for res_per_query in res:
            for r in res_per_query:
                context.append(r.payload)
                        
        query.metadata['context'] = context
        return query

