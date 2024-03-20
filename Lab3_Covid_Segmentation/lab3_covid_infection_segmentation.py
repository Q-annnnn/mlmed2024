# -*- coding: utf-8 -*-
"""Lab3_Covid_Infection_Segmentation.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1iwfdjfEqv0-uwkkQAAIIiC3m3W_EZ9kZ

### **1. Import the libraries**
"""

from google.colab import drive
drive.mount('/content/drive')

import pandas as pd
import os
import cv2
import numpy as np
import glob

import numpy as np
from matplotlib import pyplot as plt
import tifffile as tiff
from PIL import Image
import tensorflow as tf
from tensorflow import keras
! pip install segmentation_models
import os
os.environ["SM_FRAMEWORK"] = "tf.keras"

from tensorflow import keras
import segmentation_models as sm
from tensorflow.keras.metrics import MeanIoU
import random
!pip install split-folders
import splitfolders

"""### **2. Data Preprocessing**"""

seed=24
batch_size= 32
n_classes=2

from sklearn.preprocessing import MinMaxScaler
scaler = MinMaxScaler()
from keras.utils import to_categorical

#Preprocess input for transfer learning
BACKBONE = 'resnet34'
preprocess_input = sm.get_preprocessing(BACKBONE)

def preprocess_data(img, mask, num_class):
    # Scale images
    scaler = MinMaxScaler()
    img_flat = img.reshape(-1, img.shape[-1])
    img_scaled = scaler.fit_transform(img_flat).reshape(img.shape)
    img_processed = preprocess_input(img_scaled)  # Preprocess based on the pretrained backbone...

    # Ensure mask values are within the range [0, num_classes-1]
    mask = np.clip(mask, 0, num_class - 1)

    # Convert mask to one-hot
    mask_one_hot = to_categorical(mask, num_class)

    return img_processed, mask_one_hot

"""### **3. Train set and Valid set Loader**"""

from tensorflow.keras.preprocessing.image import ImageDataGenerator
def trainGenerator(train_img_path, train_mask_path, num_class):

    img_data_gen_args = dict(horizontal_flip=True,
                      vertical_flip=True,
                      fill_mode='reflect')

    image_datagen = ImageDataGenerator(**img_data_gen_args)
    mask_datagen = ImageDataGenerator(**img_data_gen_args)

    image_generator = image_datagen.flow_from_directory(
        train_img_path,
        class_mode = None,
        batch_size = batch_size,
        seed = seed)

    mask_generator = mask_datagen.flow_from_directory(
        train_mask_path,
        class_mode = None,
        color_mode = 'grayscale',
        batch_size = batch_size,
        seed = seed)

    train_generator = zip(image_generator, mask_generator)

    for (img, mask) in train_generator:
        img, mask = preprocess_data(img, mask, num_class)
        yield (img, mask)

train_img_path = "/content/drive/MyDrive/Covid_Dataset/train_images/"
train_mask_path = "/content/drive/MyDrive/Covid_Dataset/train_masks/"


val_img_path = "/content/drive/MyDrive/Covid_Dataset/val_images/"
val_mask_path = "/content/drive/MyDrive/Covid_Dataset/val_masks/"

test_img_path = '/content/drive/MyDrive/Covid_Dataset/test_images'
test_mask_path = '/content/drive/MyDrive/Covid_Dataset/test_masks'

# Create generators
train_img_gen = trainGenerator(train_img_path, train_mask_path, num_class=n_classes)
val_img_gen = trainGenerator(val_img_path, val_mask_path, num_class=n_classes)
test_img_gen = trainGenerator(test_img_path, test_mask_path, num_class=n_classes)
x, y = train_img_gen.__next__()

for i in range(0,3):
    image = x[i]
    mask = np.argmax(y[i], axis=2)

    plt.subplot(1,2,1)
    plt.imshow(image)
    plt.subplot(1,2,2)
    plt.imshow(mask, cmap='gray')
    plt.show()

x_val, y_val = val_img_gen.__next__()

for i in range(0,3):
    image = x_val[i]
    mask = np.argmax(y_val[i], axis=2)
    plt.subplot(1,2,1)
    plt.imshow(image)
    plt.subplot(1,2,2)
    plt.imshow(mask, cmap='gray')
    plt.show()

"""### **4. Unet Model Training**"""

num_train_imgs = len(os.listdir('/content/drive/MyDrive/Covid_Dataset/train_images/train/'))
num_val_images = len(os.listdir('/content/drive/MyDrive/Covid_Dataset/val_images/val/'))
steps_per_epoch = num_train_imgs//batch_size
val_steps_per_epoch = num_val_images//batch_size


IMG_HEIGHT = x.shape[1]
IMG_WIDTH  = x.shape[2]
IMG_CHANNELS = x.shape[3]

n_classes=2

from keras.callbacks import ModelCheckpoint

checkpoint_path = "/content/drive/MyDrive/covid_model_weights.h5"

checkpoint = ModelCheckpoint(filepath=checkpoint_path,
                             monitor='val_loss',
                             save_best_only=True,
                             save_weights_only=False,
                             mode='min',
                             verbose=1)

model = sm.Unet(BACKBONE, encoder_weights='imagenet',
                input_shape=(IMG_HEIGHT, IMG_WIDTH, IMG_CHANNELS),
                classes=n_classes, activation='softmax')
model.compile('Adam', loss=sm.losses.categorical_focal_jaccard_loss, metrics=[sm.metrics.iou_score])

print(model.summary())
print(model.input_shape)

from keras.models import load_model
model.compile('Adam', loss=sm.losses.categorical_focal_jaccard_loss, metrics=[sm.metrics.iou_score])
history = model.fit(train_img_gen,
                    steps_per_epoch=steps_per_epoch,
                    epochs=50,
                    verbose=1,
                    validation_data=val_img_gen,
                    validation_steps=val_steps_per_epoch,
                    callbacks=[checkpoint])

model.save('/content/drive/MyDrive/covid_batch16_2.hdf5')

"""### **5. Model Evaluation**"""

loss = history.history['loss']
val_loss = history.history['val_loss']
epochs = range(1, len(loss) + 1)
plt.plot(epochs, loss, 'y', label='Training loss')
plt.plot(epochs, val_loss, 'r', label='Validation loss')
plt.title('Training and validation loss')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.legend()
plt.show()

acc = history.history['iou_score']
val_acc = history.history['val_iou_score']

plt.plot(epochs, acc, 'y', label='Training IoU')
plt.plot(epochs, val_acc, 'r', label='Validation IoU')
plt.title('Training and validation IoU')
plt.xlabel('Epochs')
plt.ylabel('IoU')
plt.legend()
plt.show()

"""### **6. Prediction**"""

from keras.models import load_model

model = load_model("/content/drive/MyDrive/covid_model_weights.h5", compile=False)


test_image_batch, test_mask_batch = val_img_gen.__next__()

#Convert categorical to integer for visualization and IoU calculation
test_mask_batch_argmax = np.argmax(test_mask_batch, axis=3)
test_pred_batch = model.predict(test_image_batch)
test_pred_batch_argmax = np.argmax(test_pred_batch, axis=3)

n_classes = 2
IOU_keras = MeanIoU(num_classes=n_classes)
IOU_keras.update_state(test_pred_batch_argmax, test_mask_batch_argmax)
print("Mean IoU =", IOU_keras.result().numpy())

import matplotlib.pyplot as plt
import cv2

target_shape = (1024, 1024)

for img_num in range(test_image_batch.shape[0]):
    resized_test_image = cv2.resize(test_image_batch[img_num], target_shape[::-1])

    resized_test_label = cv2.resize(test_mask_batch_argmax[img_num].astype(float), target_shape[::-1], interpolation=cv2.INTER_NEAREST)

    resized_test_pred = cv2.resize(test_pred_batch_argmax[img_num].astype(float), target_shape[::-1], interpolation=cv2.INTER_NEAREST)

    fig, axs = plt.subplots(1, 3, figsize=(18, 6))

    axs[0].set_title('Testing Image')
    axs[0].imshow(resized_test_image)

    axs[1].set_title('Testing Label')
    axs[1].imshow(resized_test_label)

    axs[2].set_title('Prediction Image')
    axs[2].imshow(resized_test_pred)

    plt.show()