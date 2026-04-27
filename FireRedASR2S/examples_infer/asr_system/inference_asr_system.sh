#!/bin/bash

# Copyright 2026 Xiaohongshu. (Author: Kaituo Xu, Kai Huang, Yan Jia, Junjie Chen, Wenpeng Li)

export PATH=$PWD/fireredasr2s/:$PATH
export PYTHONPATH=$PWD/:$PYTHONPATH

# Support several input format
wavs="--wav_path wav/BAC009S0764W0121.wav"
wavs="--wav_paths wav/BAC009S0764W0121.wav wav/IT0011W0001.wav wav/TEST_NET_Y0000000000_-KTKHdZ2fb8_S00000.wav wav/TEST_MEETING_T0000000001_S00000.wav"
wavs="--wav_dir wav/"
wavs="--wav_scp wav/wav.scp"

outdir=out
mkdir -p $outdir

# vad_model_dir includes model.pth.tar, cmvn.ark
# lid_model_dir includes model.pth.tar, cmvn.ark, dict.txt
# asr_model_dir includes model.pth.tar, cmvn.ark, dict.txt
# punc_model_dir includes model.pth.tar, chinese-bert-wwm-ext_vocab.txt, chinese-lert-base, out_dict
asr_model_dir=$PWD/pretrained_models/FireRedASR2-AED
vad_model_dir=$PWD/pretrained_models/FireRedVAD/VAD
lid_model_dir=$PWD/pretrained_models/FireRedLID
punc_model_dir=$PWD/pretrained_models/FireRedPunc

asr_args="--asr_model_dir $asr_model_dir --asr_use_gpu 1 --asr_use_half 0
--asr_batch_size 16 --beam_size 3 --nbest 1
--decode_max_len 0 --softmax_smoothing 1.25 --aed_length_penalty 0.6
--eos_penalty 1.0 --return_timestamp 1"

vad_args="--enable_vad 1 --vad_model_dir $vad_model_dir --vad_use_gpu 1
--smooth_window_size 5 --speech_threshold 0.5 --min_speech_frame 20
--max_speech_frame 2000 --min_silence_frame 10 --merge_silence_frame 50
--extend_speech_frame 5 --vad_chunk_max_frame 30000"

lid_args="--enable_lid 1 --lid_model_dir $lid_model_dir --lid_use_gpu 1"

punc_args="--enable_punc 1 --punc_model_dir $punc_model_dir --punc_use_gpu 1
--punc_batch_size 32 --punc_with_timestamp 1 --punc_sentence_max_length 25"

extra_args="--write_textgrid 1 --write_srt 1 --save_segment 1"

set -x
CUDA_VISIBLE_DEVICES=0 fireredasr2s-cli $asr_args $vad_args $lid_args $punc_args $extra_args $wavs --outdir $outdir
