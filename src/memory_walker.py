import struct,glob,sys,os

from construct import *

PALPTR=0x004E3CA4 # the palette is always at this offset.

from memory_access import ProcessMemory
from brender_structures import *


class SceneBuilder(object):
	def __init__(self, memory):
		self.memory = memory
		self.scene={}

	def buildSceneFromStack(self, esp):
		self.scene = self.memory.getStructAt(esp,RenderArguments)
		self.buildScene()

	def findRenderArguments(self):
		mvie=self.getAndConfirmClass(0x4E3E74,   'MVIE')
		bwld=self.getAndConfirmClass(mvie+0x158, 'BWLD')

		self.scene = Container(
			world =  bwld+0x028,
			camera = bwld+0x084,
			pixels = bwld+0x10C,
			depth =  bwld+0x138,
		)

	def getAndConfirmClass(self, ptr, classid):
		offset=self.memory.unpack(ptr, 'L')[0]
		self.confirmClass(offset, classid)
		return offset

	def confirmClass(self, offset, classid):
		mem=self.memory
		vtable=mem.unpack(offset,'L')[0]
		getIDFunc=mem.unpack(vtable+4,'L')[0]
		idbytes=mem.read(getIDFunc+1,4)[::-1].replace('\0','_')
		if idbytes != classid:
			raise ValueError("Checked offset %d(%8X) for vtable for %s but got %s",(offset,offset,classid,idbytes))
		

	def buildScene(self):
		mem,scene = self.memory, self.scene

		palette_ptr=mem.getStructAt(PALPTR,ULInt32('palette'))

		scene['palette']=mem.getStructAt(palette_ptr,PALETTE)
		

		scene['world']=self.buildTree(scene['world'])
		scene['camera']=self.buildTree(scene['camera'])

		cm=scene['pixels']=mem.getStructAt(scene['pixels'],Pixelmap)
		if cm['pixels']!=0:
			cm['pixels']=mem.getRawImage(cm['width'],cm['height'],cm['pixels'])
		
		cm=scene['depth']=mem.getStructAt(scene['depth'],Pixelmap)
		if cm['pixels']!=0:
			cm['depth_pixels']=mem.getGreyscale(cm['width'],cm['height'],cm['pixels'])


	def buildTree(self, parent):
		mem = self.memory
		actor = mem.getActorAt(parent)
		if actor['type_data']!=0:
			if actor['actor_type']=='BR_ACTOR_CAMERA':
				actor['camera'] = mem.getStructAt(actor['type_data'],Camera)
			if actor['actor_type']=='BR_ACTOR_LIGHT':
				actor['light'] = mem.getStructAt(actor['type_data'],Light)
		if actor['actor_type']=='BR_ACTOR_MODEL':
			if actor['model']!=0:
				model=actor['model']=mem.getStructAt(actor['model'],Model)
				model['vertices']=mem.collectArray(model['prepared_vertices'],model['nprepared_vertices'],Vertex)
				model['faces']=mem.collectArray(model['prepared_faces'],model['nprepared_faces'],Face)
				model['face_groups']=mem.collectArray(model['face_groups'],model['nface_groups'],FaceGroup)

		if actor['material']!=0:
			actor['material'] = mem.getStructAt(actor['material'],Material)
			actor['material'].colors = self.decodeColorRange(actor['material'])
			if actor['material']['color_map']!=0:
				cm=actor['material']['color_map']=mem.getStructAt(actor['material']['color_map'],Pixelmap)
				if cm['pixels']!=0:
					cm['pixels']=mem.getRawImage(cm['width'],cm['height'],cm['pixels'])
		if actor['children']!=0:
			actor['children']=self.collectChildren(actor)
		return actor

	def collectChildren(self, obj):
		kids=[]
		current=obj['children']
		while current!=0:
			kid=self.buildTree(current)
			kids.append(kid)
			current=kid['next']
		return kids

	def decodeColorRange(self, material):
		pal = self.scene['palette']

		if material['index_range']==0:
			return []

		out=[]

		for i in range(material['index_base'],material['index_base']+material['index_range']):
			p=pal[i]
			out.append((p.r,p.g,p.b))

		return out 



if __name__=='__main__':
	memory = ProcessMemory()
	sceneb = SceneBuilder(memory)
	sceneb.findRenderArguments()
	sceneb.buildScene()
