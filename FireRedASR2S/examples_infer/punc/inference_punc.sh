#!/bin/bash

# Copyright 2026 Xiaohongshu. (Author: Kaituo Xu, Junjie Chen)

export PATH=$PWD/fireredpunc/:$PATH
export PYTHONPATH=$PWD/:$PYTHONPATH

# model_dir includes model.pth.tar
model_dir=$PWD/pretrained_models/FireRedPunc

# Usage 1
CUDA_VISIBLE_DEVICES=0 add_punc.py --model_dir $model_dir $args --input_txt "你好世界 How are you I'm fine thanks" --output ""


# Usage 2
in="--input_file txt/nopunc.txt --input_contain_uttid 0"
out=out/punc.txt

if [ ! -z $out ]; then
    mkdir -p $(dirname $out)
fi
set -x

args="--use_gpu 1 --batch_size 32 --sentence_max_length -1"
CUDA_VISIBLE_DEVICES=0 add_punc.py --model_dir $model_dir $args $in --output "$out"
