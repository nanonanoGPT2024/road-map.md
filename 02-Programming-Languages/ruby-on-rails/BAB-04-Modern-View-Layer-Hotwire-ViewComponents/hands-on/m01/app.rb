# frozen_string_literal: true

class ItemsController < ApplicationController
  before_action :set_item, only: %i[show edit update destroy toggle]

  def index
    @items = Item.order(created_at: :desc)
    @new_item = Item.new
  end

  def create
    @item = Item.new(item_params)

    if @item.save
      respond_to do |format|
        format.turbo_stream
        format.html { redirect_to items_path, notice: "Item berhasil dibuat." }
      end
    else
      render :new, status: :unprocessable_entity
    end
  end

  def update
    if @item.update(item_params)
      respond_to do |format|
        format.turbo_stream
        format.html { redirect_to items_path }
      end
    else
      render :edit, status: :unprocessable_entity
    end
  end

  def toggle
    @item.update(completed: !@item.completed)
    respond_to do |format|
      format.turbo_stream { render turbo_stream: turbo_stream.replace(@item, ShoppingItemComponent.new(item: @item)) }
      format.html { redirect_to items_path }
    end
  end

  def destroy
    @item.destroy
    respond_to do |format|
      format.turbo_stream { render turbo_stream: turbo_stream.remove(@item) }
      format.html { redirect_to items_path }
    end
  end

  private

  def set_item
    @item = Item.find(params[:id])
  end

  def item_params
    params.require(:item).permit(:name, :quantity, :completed)
  end
end
