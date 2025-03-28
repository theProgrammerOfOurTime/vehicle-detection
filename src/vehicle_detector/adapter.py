import numpy as np
import cv2 as cv
from abc import ABC, abstractmethod

class Adapter(ABC):
    def __init__(self, conf, nms, class_names, interest_classes = None):
        if interest_classes == None:
            interest_classes = ['car', 'bus', 'truck']
        self.conf = conf
        self.nms = nms
        self.class_names = class_names
        self.interest_classes = interest_classes
        
    @abstractmethod
    def postProcessing(self, output, image_width, image_height):
        pass
    
    def _nms(self, boxes, confidences, classes_id):
        indexes = cv.dnn.NMSBoxes(boxes, confidences, self.conf, self.nms)
        bboxes = []
        for i in indexes:
            bboxes.append((classes_id[i], int(boxes[i][0]), int(boxes[i][1]), int(boxes[i][2]), int(boxes[i][3]), confidences[i]))
            
        return bboxes
        

class AdapterDetectionTask(Adapter):
    
    def __init__(self, conf, nms, class_names, interest_classes = None):
        super().__init__(conf, nms, class_names, interest_classes)

    def postProcessing(self, output, image_width, image_height):
        classes_id = []
        confidences = []
        boxes = []
        numDetections = output.shape[2]
        for i in range(numDetections):
            box = output[0, 0, i]
            confidence = box[2]
            if confidence > self.conf:
                class_id = int(box[1])
               
                left = min(int(box[3] * image_width), image_width)
                top = min(int(box[4] * image_height), image_height)
                right = min(int(box[5] * image_width), image_width)
                bottom = min(int(box[6] * image_height), image_height)
                
                class_name = self.class_names[int(class_id)]
                
                if class_name in self.interest_classes:
                    boxes.append((left, top, right, bottom))
                    classes_id.append(class_name)
                    confidences.append(confidence)
                    
        return self._nms(boxes, confidences, classes_id)


class AdapterYOLO(Adapter):
    
    def __init__(self, conf, nms, class_names, interest_classes = None):
        super().__init__(conf, nms, class_names, interest_classes)
    
    def postProcessing(self, output, image_width, image_height):
        classes_id = []
        boxes = []
        confidences = []
        for detection in output:

            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            class_name = self.class_names[class_id]
            if confidence > self.conf:

                cx1 = int(detection[0] * image_width)
                cy1 = int(detection[1] * image_height)
                w = int(detection[2] * image_width)
                h = int(detection[3] * image_height)          

                if class_name in self.interest_classes:
                    boxes.append((cx1 - w // 2, cy1 - h // 2, cx1 + w // 2, cy1 + h // 2))
                    classes_id.append(class_name)
                    confidences.append(confidence)
                    
        return self._nms(boxes, confidences, classes_id)  

class AdapterYOLOTiny(Adapter):
    
    def __init__(self, conf, nms, class_names, interest_classes = None):
        super().__init__(conf, nms, class_names, interest_classes)       

    def __demo_postprocess(self, outputs, img_size, p6=False):
        grids = []
        expanded_strides = []
        strides = [8, 16, 32] if not p6 else [8, 16, 32, 64]
        hsizes = [img_size[0] // stride for stride in strides]
        wsizes = [img_size[1] // stride for stride in strides]

        for hsize, wsize, stride in zip(hsizes, wsizes, strides):
            xv, yv = np.meshgrid(np.arange(wsize), np.arange(hsize))
            grid = np.stack((xv, yv), 2).reshape(1, -1, 2)
            grids.append(grid)
            shape = grid.shape[:2]
            expanded_strides.append(np.full((*shape, 1), stride))

        grids = np.concatenate(grids, 1)
        expanded_strides = np.concatenate(expanded_strides, 1)
        outputs[..., :2] = (outputs[..., :2] + grids) * expanded_strides
        outputs[..., 2:4] = np.exp(outputs[..., 2:4]) * expanded_strides
        return outputs

    def postProcessing(self, output, image_width, image_height):
        
        predictions = self.__demo_postprocess(output[0], (416, 416))
        rh = 416 / image_height
        rw = 416 / image_width
        boxes = predictions[:, :4]
        scores = predictions[:, 4:5] * predictions[:, 5:]
        boxes_xyxy = np.ones_like(boxes)
        
        boxes_xyxy[:, 0] = boxes[:, 0] / rw - boxes[:, 2]/2. / rw
        boxes_xyxy[:, 1] = boxes[:, 1] / rh - boxes[:, 3]/2. / rh
        boxes_xyxy[:, 2] = boxes[:, 0] / rw + boxes[:, 2]/2. / rw
        boxes_xyxy[:, 3] = boxes[:, 1] / rh + boxes[:, 3]/2. / rh
        
        all_classes_id = scores.argmax(1)
        all_confidences = scores[np.arange(len(all_classes_id)), all_classes_id]
        
        classes_id = []
        boxes = []
        confidences = []
        for i, class_id in zip(range(len(all_classes_id)), all_classes_id):
            if self.class_names[class_id] in self.interest_classes:
                classes_id.append(self.class_names[class_id])
                boxes.append(boxes_xyxy[i])
                confidences.append(all_confidences[i])
        
        return self._nms(boxes, confidences, classes_id)